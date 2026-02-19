# Client

React frontend for Trip Planner AI. Chat interface for the travel planning agent with a live reasoning panel showing tool call details.

## Tech Stack

- React 19, TypeScript
- Vite + `@tailwindcss/vite`
- Tailwind CSS (utility classes + CSS custom properties for theming)
- Lucide React (icons)

## Project Structure

```
src/
├── App.tsx                    # Root component — state, API call, layout
├── main.tsx                   # React entry point
├── types.ts                   # Message and ReasoningStep interfaces
├── index.css                  # Design tokens, reset, animations
└── components/
    ├── MessageBubble.tsx      # Renders user and assistant messages, inline markdown
    ├── ReasoningPanel.tsx     # Collapsible tool call trace (steps + model thinking)
    └── ChatInput.tsx          # Auto-resizing textarea with send button
```

## Key Features

- Natural language travel planning via a multi-step AI agent
- Inline markdown rendering — headings, bullets, numbered lists, bold, links
- Reasoning panel — shows every tool the agent called, with input and output
- Follow-up suggestion chips after each assistant response
- Welcome screen with starter prompts
- Session memory — last 40 messages sent as history context
- Rate limit error card with reset date displayed on 429
- Dark theme with CSS custom properties

## Component Overview

**`App.tsx`**
Owns all state. Calls `POST /plan` with the message and conversation history, strips `<thinking>` tags from the model response, updates the message list.

**`MessageBubble.tsx`**
Three render paths: user bubble (right-aligned), loading dots, assistant message (full-width). Assistant messages go through a lightweight markdown parser that handles `##`/`###`/`####` headings, `-`/`*` bullets, numbered lists, `**bold**`, and `[label](url)` links.

**`ReasoningPanel.tsx`**
Collapsible panel showing the agent reasoning block and each tool call as an expandable row with the raw JSON input/output.

**`ChatInput.tsx`**
Textarea that auto-resizes up to 200px. Enter sends, Shift+Enter adds a line break.

## Development

```bash
npm install
npm run dev
```

Runs on `http://localhost:5173`. Vite proxies `/plan`, `/health`, and `/usage` to `http://localhost:8000` so no CORS config is needed locally.

Backend must be running first — see [server setup](../server/README.md).

### Environment Variables

Create `.env.local` for a custom backend URL (optional — Vite proxy handles it in dev):

```env
VITE_API_URL=https://your-app-runner-url.awsapprunner.com
```

Leave blank to use the Vite proxy during local development.

## Deployment (AWS Amplify)

1. Connect repo to Amplify, set **App root directory** to `client`
2. Amplify auto-detects Vite — verify build settings:

```yaml
version: 1
frontend:
  phases:
    preBuild:
      commands:
        - npm install
    build:
      commands:
        - npm run build
  artifacts:
    baseDirectory: dist
    files:
      - '**/*'
  cache:
    paths:
      - node_modules/**/*
appRoot: client
```

3. Add environment variable in Amplify console:

| Key | Value |
|---|---|
| `VITE_API_URL` | Your App Runner backend URL |

4. After setting the variable, trigger a redeploy — Vite bakes env vars at build time.

## Scripts

- `npm run dev` — Start dev server with hot reload
- `npm run build` — Production build to `dist/`
- `npm run preview` — Preview production build locally
- `npm run lint` — Run ESLint
