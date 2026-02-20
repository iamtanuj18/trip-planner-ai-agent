# Server

FastAPI backend for Trip Planner AI. Runs a LangGraph agent that routes travel queries to the appropriate tool sequence, streams results back via SSE, and stores conversation history in DynamoDB.

## Tech stack

- Python 3.11, FastAPI, Uvicorn
- LangGraph (agent graph), LangChain AWS (Bedrock integration)
- AWS Bedrock — Amazon Nova Lite (`us.amazon.nova-lite-v1:0`, us-east-1)
- DynamoDB for session storage (ap-southeast-2)
- LangSmith for tracing
- boto3, python-dotenv, mangum, tzdata

## File structure

```
server/
├── main.py            # FastAPI app — endpoints, rate limiting, session storage
├── agent.py           # LangGraph graph — nodes, routing logic, system prompt
├── tools.py           # LangChain tools the agent can call
├── knowledge_base.py  # In-memory KB — 22 destinations, activities, AUD pricing
├── data/
│   └── destinations.json
├── apprunner.yaml     # App Runner build and run config
├── requirements.txt
└── .env.example
```

## Agent architecture

The graph has two nodes — `_agent_node` and `_tool_node` — connected in a loop:

```
user message
     ↓
_agent_node   checks which tools have run, infers intent, picks _llm_plan or _llm_free
     ↓ (if tool calls present)
_tool_node    executes tools, appends ToolMessages to state
     ↓
_agent_node   (loop until no more tool calls)
     ↓
final response streamed to client
```

Two LLM bindings are used:

- `_llm_plan` — tools attached, `tool_choice=auto`. Used when the agent must gather more data.
- `_llm_free` — no tools attached. Used on the final composing pass so the model cannot trigger another tool call.

**Intent routing in `_agent_node`** (runs after every `ToolMessage`):

| Condition | Action |
|---|---|
| `build_itinerary` already called | Switch to `_llm_free`, compose full plan |
| Only `list_available_destinations` was called | Switch to `_llm_free`, compose conversational reply |
| Two `search_destinations` calls, no `estimate_budget` | Switch to `_llm_free`, compose comparison |
| `estimate_budget` called, feasibility keywords in message | Switch to `_llm_free`, answer budget question |
| `estimate_budget` called, no feasibility keywords | Stay on `_llm_plan`, continue to `get_activities` |
| 5+ tool messages | Switch to `_llm_free` as a safety cap |

## Tools

| Tool | What it does |
|---|---|
| `search_destinations` | Filters the KB by interests, budget level, season, region, or country |
| `estimate_budget` | Calculates total AUD cost — flights, accommodation, food, activities, transport |
| `get_activities` | Returns curated activities and highlights for a destination |
| `build_itinerary` | Builds a day-by-day schedule with morning/afternoon/evening slots |
| `list_available_destinations` | Returns all 22 destination names — used for greetings and off-topic paths |

## Knowledge base

22 destinations in `data/destinations.json` spanning Asia, Europe, the Americas, Oceania, and Africa/Middle East. Each entry includes region, country, visa notes for Australian passport holders, best travel seasons, budget/mid-range/luxury AUD daily costs, average flight cost from Australia in AUD, and a pool of curated activities.

All cost figures are stored in USD and converted to AUD at a fixed rate defined in `knowledge_base.py`.

## Session storage

Conversation history is stored in DynamoDB with a 24-hour TTL on each item so sessions expire automatically. The table name and region are set via env vars. If `SESSIONS_TABLE` is not set (local dev), an in-memory dict is used as a fallback.

Required DynamoDB table schema:
- Partition key: `session_id` (String)
- TTL attribute: `ttl` (Number)

The App Runner IAM role needs `dynamodb:GetItem` and `dynamodb:PutItem` on the table.

## LangSmith tracing

In production, the LangSmith API key is fetched from AWS Secrets Manager at startup using the secret name in `LANGSMITH_SECRET_NAME`. The key never appears in source code or environment variable configs. Locally, set `LANGSMITH_API_KEY` directly in `.env`.

If the Secrets Manager fetch fails, the app continues without tracing — it is not a hard dependency.

## Rate limiting

Two counters kept in memory, both reset on Melbourne time:

| Counter | Default | Resets |
|---|---|---|
| Daily | 50 requests | Midnight Melbourne |
| Monthly | 500 requests | 1st of the month, Melbourne |

A `429` response includes a structured `detail` with `type`, `message`, and `resets_at` so the frontend can show a user-friendly error card.

## API endpoints

```
POST /stream   Body: { message, session_id }  →  SSE stream of tool_start / tool_end / token events
POST /plan     Body: { message, session_id }  →  { response, reasoning_steps }
GET  /health   →  { status: "ok" }
GET  /usage    →  { daily: { used, limit, resets_at }, monthly: { used, limit, resets_at } }
```

`/stream` is the primary endpoint used by the frontend. `/plan` is a non-streaming fallback.

## Development

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
cp .env.example .env         # fill in your values
uvicorn main:app --reload --port 8000
```

### Environment variables

See `.env.example` for the full list. Required for local development:

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
ALLOWED_ORIGINS=http://localhost:5173
```

Optional (used in production, safe to leave blank locally):

```env
SESSIONS_TABLE=trip-planner-sessions
DYNAMODB_REGION=ap-southeast-2
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=trip-planner-ai
LANGSMITH_SECRET_NAME=           # production only, replaces LANGSMITH_API_KEY
```

On App Runner, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are not needed — the attached IAM role provides credentials automatically.

## Deployment (AWS App Runner)

Build and run config lives in `apprunner.yaml`. App Runner reads this file automatically when the service is connected to the repo.

The App Runner IAM role needs:
- `bedrock:InvokeModel` on `us.amazon.nova-lite-v1:0` (us-east-1)
- `dynamodb:GetItem`, `dynamodb:PutItem` on the sessions table (ap-southeast-2)
- `secretsmanager:GetSecretValue` on the LangSmith secret (ap-southeast-2)

Environment variables set in the App Runner console (not committed to the repo):

| Variable | Value |
|---|---|
| `ALLOWED_ORIGINS` | Amplify frontend URL |
| `SESSIONS_TABLE` | DynamoDB table name |
| `DYNAMODB_REGION` | `ap-southeast-2` |
| `LANGSMITH_SECRET_NAME` | Secrets Manager secret name holding the LangSmith API key |
