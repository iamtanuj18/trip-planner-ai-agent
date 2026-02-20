import json
import os
import re
import time as _time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from mangum import Mangum
from pydantic import BaseModel
from dotenv import load_dotenv

from agent import run_agent, arun_agent

load_dotenv()

# Load LangSmith key from Secrets Manager when running on App Runner.
# apprunner.yaml is committed to git so secrets can't go in there directly;
# LANGSMITH_SECRET_NAME holds only the secret name (safe to commit), and the
# actual key is fetched once at startup. Locally LANGSMITH_API_KEY comes from .env,
# so LANGSMITH_SECRET_NAME is unset and this block is skipped entirely.
_SM_SECRET_NAME = os.getenv("LANGSMITH_SECRET_NAME", "")
if _SM_SECRET_NAME and not os.environ.get("LANGSMITH_API_KEY"):
    try:
        _sm = boto3.client(
            "secretsmanager",
            region_name=os.getenv("DYNAMODB_REGION", "ap-southeast-2"),
        )
        os.environ["LANGSMITH_API_KEY"] = _sm.get_secret_value(SecretId=_SM_SECRET_NAME)["SecretString"]
        os.environ["LANGSMITH_TRACING"]   = "true"
        os.environ["LANGSMITH_PROJECT"]   = os.getenv("LANGSMITH_PROJECT", "trip-planner-ai")
    except Exception:
        pass  # tracing just won't activate — the app itself still runs fine

app = FastAPI(title="Trip Planner AI")

_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173")
_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

_MELBOURNE_TZ  = ZoneInfo("Australia/Melbourne")
_MAX_DAILY     = int(os.getenv("MAX_DAILY_REQUESTS",   "50"))
_MAX_MONTHLY   = int(os.getenv("MAX_MONTHLY_REQUESTS", "500"))

_daily:   dict = {"date":  date.today(),                "count": 0}
_monthly: dict = {"month": date.today().replace(day=1), "count": 0}

# Session storage — DynamoDB in production, in-memory dict locally.
_SESSIONS_TABLE_NAME = os.getenv("SESSIONS_TABLE", "")
_dynamo_table = None

if _SESSIONS_TABLE_NAME:
    try:
        _dynamo_table = boto3.resource(
            "dynamodb",
            region_name=os.getenv("DYNAMODB_REGION", os.getenv("AWS_REGION", "us-east-1")),
        ).Table(_SESSIONS_TABLE_NAME)
    except Exception:
        pass

_sessions_mem: dict[str, list[dict]] = {}
_SESSION_MAX = 40


def _get_session(sid: str) -> list[dict]:
    if _dynamo_table and sid:
        try:
            resp = _dynamo_table.get_item(Key={"session_id": sid})
            return resp.get("Item", {}).get("history", [])
        except Exception:
            pass
    return _sessions_mem.get(sid, []) if sid else []


def _put_session(sid: str, history: list[dict]) -> None:
    if _dynamo_table and sid:
        try:
            _dynamo_table.put_item(Item={
                "session_id": sid,
                "history":    history,
                "ttl":        int(_time.time()) + 86400,  # auto-expire after 24 h
            })
            return
        except Exception:
            pass
    if sid:
        _sessions_mem[sid] = history


def _fmt_reset(dt: datetime) -> str:
    return dt.strftime(f"%A {dt.day} %B %Y at 12:00 AM %Z")


def _check_rate_limit() -> None:
    today      = date.today()
    this_month = today.replace(day=1)

    if _daily["date"] != today:
        _daily["date"]  = today
        _daily["count"] = 0

    if _monthly["month"] != this_month:
        _monthly["month"] = this_month
        _monthly["count"] = 0

    if _monthly["count"] >= _MAX_MONTHLY:
        now = datetime.now(_MELBOURNE_TZ)
        if now.month == 12:
            reset_dt = now.replace(year=now.year + 1, month=1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        else:
            reset_dt = now.replace(month=now.month + 1, day=1,
                                   hour=0, minute=0, second=0, microsecond=0)
        raise HTTPException(
            status_code=429,
            detail={
                "type":      "monthly_limit",
                "message":   f"Monthly limit of {_MAX_MONTHLY} requests reached.",
                "resets_at": _fmt_reset(reset_dt),
            },
        )

    if _daily["count"] >= _MAX_DAILY:
        now      = datetime.now(_MELBOURNE_TZ)
        reset_dt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        raise HTTPException(
            status_code=429,
            detail={
                "type":      "daily_limit",
                "message":   f"Daily limit of {_MAX_DAILY} requests reached.",
                "resets_at": _fmt_reset(reset_dt),
            },
        )

    _daily["count"]   += 1
    _monthly["count"] += 1


def _partial_tag_len(text: str, tag: str) -> int:
    """Returns how many trailing chars of text could be the start of tag."""
    max_n = min(len(text), len(tag) - 1)
    for n in range(max_n, 0, -1):
        if text.endswith(tag[:n]):
            return n
    return 0


def _extract_suggestions(text: str) -> tuple[str, list[str]]:
    # Strip any <thinking> blocks the filter may have missed (e.g. from /plan endpoint).
    text = re.sub(r"<thinking>[\s\S]*?</thinking>", "", text, flags=re.DOTALL).strip()

    suggestions: list[str] = []

    # Primary format: <suggestions>[...]</suggestions>
    match = re.search(r"<suggestions>\s*(\[[\s\S]*?\])\s*</suggestions>", text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            if isinstance(parsed, list):
                suggestions = [s for s in parsed if isinstance(s, str)]
        except (json.JSONDecodeError, ValueError):
            pass
        text = re.sub(r"<suggestions>[\s\S]*?</suggestions>", "", text, flags=re.DOTALL)

    # Fallback: model wrote "Suggestions\n[...]" without XML tags.
    if not suggestions:
        bare = re.search(r"\n\*{0,3}[Ss]uggestions?\*{0,3}\s*\n\s*(\[[\s\S]*?\])", text)
        if bare:
            try:
                parsed = json.loads(bare.group(1))
                if isinstance(parsed, list):
                    suggestions = [s for s in parsed if isinstance(s, str)]
            except (json.JSONDecodeError, ValueError):
                pass
            text = text[:bare.start()].rstrip()

    # Last resort: bare JSON array at the very end of the text.
    if not suggestions:
        tail = re.search(r"\n(\[\"[\s\S]*?\"\])\s*$", text, re.DOTALL)
        if tail:
            try:
                parsed = json.loads(tail.group(1))
                if isinstance(parsed, list) and all(isinstance(s, str) for s in parsed):
                    suggestions = parsed
                    text = text[:tail.start()].rstrip()
            except (json.JSONDecodeError, ValueError):
                pass

    return text.strip(), suggestions


class Message(BaseModel):
    role: str
    content: str


class PlanRequest(BaseModel):
    message: str
    session_id: str | None = None
    history: list[Message] = []


class PlanResponse(BaseModel):
    response: str
    reasoning_steps: list[dict]
    follow_up_suggestions: list[str] = []


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/usage")
def usage():
    return {
        "date":             str(_daily["date"]),
        "requests_today":   _daily["count"],
        "daily_limit":      _MAX_DAILY,
        "daily_remaining":  max(0, _MAX_DAILY   - _daily["count"]),
        "month":            str(_monthly["month"]),
        "requests_month":   _monthly["count"],
        "monthly_limit":    _MAX_MONTHLY,
        "monthly_remaining": max(0, _MAX_MONTHLY - _monthly["count"]),
    }


@app.post("/plan", response_model=PlanResponse)
def plan(body: PlanRequest):
    _check_rate_limit()

    sid = body.session_id
    history = (
        _get_session(sid)
        if sid
        else [{"role": m.role, "content": m.content} for m in body.history]
    )

    try:
        result = run_agent(user_message=body.message, history=history)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    clean_response, suggestions = _extract_suggestions(result["response"])

    if sid:
        updated = history + [
            {"role": "user",      "content": body.message},
            {"role": "assistant", "content": clean_response},
        ]
        _put_session(sid, updated[-_SESSION_MAX:])

    return PlanResponse(
        response=clean_response,
        reasoning_steps=result["reasoning_steps"],
        follow_up_suggestions=suggestions,
    )


@app.post("/stream")
async def stream_plan(body: PlanRequest):
    _check_rate_limit()

    sid = body.session_id
    history = (
        _get_session(sid)
        if sid
        else [{"role": m.role, "content": m.content} for m in body.history]
    )

    async def generate():
        full_text    = ""
        pending      = ""   # chars buffered pending tag detection
        in_thinking  = False
        thinking_buf = ""

        try:
            async for evt in arun_agent(body.message, history):
                if evt["type"] != "token":
                    yield f"data: {json.dumps(evt)}\n\n"
                    continue

                # Strip <thinking> blocks inline; forward as a separate event.
                pending += evt["text"]

                while pending:
                    tag = "</thinking>" if in_thinking else "<thinking>"
                    pos = pending.find(tag)

                    if pos >= 0:
                        chunk   = pending[:pos]
                        pending = pending[pos + len(tag):]

                        if in_thinking:
                            thinking_buf += chunk
                            in_thinking   = False
                            yield f'data: {json.dumps({"type": "thinking", "text": thinking_buf.strip()})}\n\n'
                            thinking_buf  = ""
                        else:
                            if chunk:
                                full_text += chunk
                                yield f'data: {json.dumps({"type": "token", "text": chunk})}\n\n'
                            in_thinking = True
                    else:
                        # No complete tag yet — hold back chars that might be a partial tag.
                        hold    = _partial_tag_len(pending, tag)
                        out     = pending[:len(pending) - hold]
                        pending = pending[len(pending) - hold:]

                        if in_thinking:
                            thinking_buf += out
                        elif out:
                            full_text += out
                            yield f'data: {json.dumps({"type": "token", "text": out})}\n\n'
                        break

        except Exception as exc:
            yield f'data: {json.dumps({"type": "error", "message": str(exc)})}\n\n'
            return

        # Flush any remaining visible text.
        if pending and not in_thinking:
            full_text += pending

        clean_response, suggestions = _extract_suggestions(full_text)
        yield f'data: {json.dumps({"type": "done", "clean_response": clean_response, "follow_up_suggestions": suggestions})}\n\n'

        if sid:
            updated = history + [
                {"role": "user",      "content": body.message},
                {"role": "assistant", "content": clean_response},
            ]
            _put_session(sid, updated[-_SESSION_MAX:])

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


handler = Mangum(app)
