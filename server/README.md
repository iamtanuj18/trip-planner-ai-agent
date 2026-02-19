# Server

FastAPI backend for Trip Planner AI. Runs a LangGraph ReAct agent that plans travel itineraries using a curated knowledge base and AWS Bedrock.

## Tech Stack

- Python 3.11+, FastAPI, Uvicorn
- LangGraph (agent orchestration)
- LangChain AWS (Bedrock integration)
- AWS Bedrock — Amazon Nova Lite (`us.amazon.nova-lite-v1:0`)
- boto3, python-dotenv, tzdata

## Architecture

```
server/
├── main.py              # FastAPI app, rate limiting, /plan /health /usage endpoints
├── agent.py             # LangGraph ReAct graph — nodes, edges, system prompt
├── tools.py             # 5 LangChain tools the agent can call
├── knowledge_base.py    # In-memory KB — 22 destinations, activities, pricing, budget tiers
├── data/
│   └── destinations.json  # Raw destination data loaded by the KB
├── requirements.txt
└── .env.example
```

## How the Agent Works

The agent runs a **ReAct loop** (Reason + Act) via LangGraph:

```
user message
     ↓
_agent_node  →  decides which tool(s) to call
     ↓
_tool_node   →  executes tools, returns structured results
     ↓
_agent_node  →  synthesises results, decides if done
     ↓
final response
```

Each response includes the full tool call trace (tool name, input, output) which the frontend exposes in the reasoning panel.

## Tools

| Tool | Description |
|---|---|
| `get_destinations` | Filters destinations by region, vibe, budget tier, and travel month |
| `get_activities` | Returns top activities and highlights for a destination |
| `build_itinerary` | Builds an N-day itinerary with morning/afternoon/evening activity slots, cycling through the available pool |
| `compare_destinations` | Side-by-side cost and vibe comparison of two or more destinations |
| `get_budget_estimate` | Calculates total and daily estimated cost in AUD for a trip |

## Knowledge Base

22 destinations stored in `data/destinations.json`, covering Asia, Europe, Pacific, the Americas, and the Middle East. Each destination includes:

- Region, country, typical travel months
- Vibe tags (beach, culture, food, adventure, etc.)
- Budget tier (budget / mid-range / luxury) with USD/day cost
- List of activities with duration and highlight flags

## Rate Limiting

Two counters stored in memory, both reset on Melbourne time:

| Limit | Default | Resets |
|---|---|---|
| Daily | 50 requests | Midnight Melbourne |
| Monthly | 500 requests | 1st of month Melbourne |

A `429` response includes a structured `detail` object with `type`, `message`, and `resets_at` so the frontend can display a user-friendly message.

## API Endpoints

```
POST /plan        Body: { message, session_id, history }  →  { response, reasoning_steps, follow_up_suggestions }
GET  /health      →  { status: "ok" }
GET  /usage       →  { daily: { used, limit, resets_at }, monthly: { ... } }
```

## Development

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --port 8000
```

### Environment Variables

Create `.env` from `.env.example`:

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key-id
AWS_SECRET_ACCESS_KEY=your-secret-access-key
BEDROCK_MODEL_ID=us.amazon.nova-lite-v1:0
MAX_DAILY_REQUESTS=50
MAX_MONTHLY_REQUESTS=500
```

The IAM user/role needs `bedrock:InvokeModel` permission on `us.amazon.nova-lite-v1:0`.

On App Runner, `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are not needed — the attached IAM role handles auth automatically.

## Deployment (AWS App Runner)

1. Push repo to GitHub
2. Create an App Runner service — source: GitHub, root directory: `server`
3. Set build command: `pip install -r requirements.txt`
4. Set start command: `uvicorn main:app --host 0.0.0.0 --port 8080`
5. Attach an IAM role with `bedrock:InvokeModel` permission
6. Set environment variables: `BEDROCK_MODEL_ID`, `MAX_DAILY_REQUESTS`, `MAX_MONTHLY_REQUESTS`
