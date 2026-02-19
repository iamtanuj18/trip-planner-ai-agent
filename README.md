# Trip Planner AI

An AI travel planning agent that builds personalised day-by-day itineraries, compares destinations, and estimates costs — all in one conversation. Powered by a multi-step ReAct agent running on AWS Bedrock.

## 🚀 [Live Demo](https://placeholder.amplifyapp.com)

Try it out: **[placeholder.amplifyapp.com](https://placeholder.amplifyapp.com)**

## What's This?

Type a natural language travel request — "7 days in Japan under A$5,000" or "best beach trip from Australia in winter" — and the agent plans your trip step by step. It searches a curated knowledge base of 22 destinations, runs multiple tool calls to gather activities and pricing, then builds a full itinerary with a daily cost breakdown. Follow-up questions are supported across the full conversation.

## Tech Stack

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS
- **Backend**: Python, FastAPI, LangGraph
- **AI**: AWS Bedrock — Amazon Nova Lite (`us.amazon.nova-lite-v1:0`)
- **Agent pattern**: ReAct (Reason + Act) loop with 5 specialised tools

## Project Structure

```
├── client/          # React + Vite frontend
├── server/          # FastAPI + LangGraph backend
└── .gitignore
```

## How the Agent Works

1. User sends a travel question
2. Agent decides which tool(s) to call — e.g. `get_destinations` → `get_activities` → `build_itinerary`
3. Tools query the knowledge base and return structured data
4. Agent synthesises results into a natural language response with itinerary and costs
5. Reasoning steps and tool call details are exposed in the UI

The frontend's reasoning panel shows exactly what tools were called and what they returned for each response.

## Deployment

### Frontend
Deployed on **AWS Amplify**
- Auto-deploys from `main` branch when `client/` changes
- `VITE_API_URL` set as environment variable pointing to the App Runner backend

### Backend
Deployed on **AWS App Runner**
- Runs the FastAPI server directly — no Lambda adapters, no cold-start timeouts
- IAM role grants `bedrock:InvokeModel` permission without storing AWS keys
- Environment variables (`BEDROCK_MODEL_ID`, rate limit config) set in App Runner console

## Local Development

### Prerequisites
- Python 3.11+
- Node.js 18+
- AWS account with Bedrock access to `us.amazon.nova-lite-v1:0`

### Backend

```bash
cd server
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
cp .env.example .env            # Fill in your AWS credentials and region
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd client
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies `/plan`, `/health`, `/usage` to the backend automatically.

## More Info

- [Client Documentation](client/README.md)
- [Server Documentation](server/README.md)
