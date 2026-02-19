import json
import os
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from pydantic import BaseModel
from dotenv import load_dotenv

from agent import run_agent

load_dotenv()

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

_sessions: dict[str, list[dict]] = {}
_SESSION_MAX_MESSAGES = 40


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


def _extract_suggestions(text: str) -> tuple[str, list[str]]:
    pattern = r"<suggestions>\s*(\[.*?\])\s*</suggestions>"
    match = re.search(pattern, text, re.DOTALL)
    if not match:
        return text.strip(), []
    try:
        suggestions = json.loads(match.group(1))
        clean = re.sub(pattern, "", text, flags=re.DOTALL).strip()
        return clean, suggestions if isinstance(suggestions, list) else []
    except (json.JSONDecodeError, ValueError):
        return text.strip(), []


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
        _sessions[sid]
        if sid and sid in _sessions
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
        _sessions[sid] = updated[-_SESSION_MAX_MESSAGES:]

    return PlanResponse(
        response=clean_response,
        reasoning_steps=result["reasoning_steps"],
        follow_up_suggestions=suggestions,
    )


handler = Mangum(app)
