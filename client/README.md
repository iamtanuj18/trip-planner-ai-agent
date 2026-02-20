# Client

React frontend for Trip Planner AI. Chat interface with real-time SSE streaming, per-tool status indicators, and a collapsible reasoning panel showing every tool call the agent made.

## Tech stack

- React 19, TypeScript
- Vite + `@tailwindcss/vite`
- Tailwind CSS with CSS custom properties for theming
- Lucide React for icons

## Project structure

```
src/
├── App.tsx                    # Root component — all state, SSE streaming, session management
├── main.tsx                   # React entry point
├── types.ts                   # Message, ReasoningStep type definitions
├── index.css                  # Design tokens, reset, animations (blinking cursor etc.)
└── components/
    ├── MessageBubble.tsx      # Renders user and assistant messages with inline markdown
    ├── ReasoningPanel.tsx     # Collapsible tool call trace with JSON input/output
    └── ChatInput.tsx          # Auto-resizing textarea, Enter to send
```

## How it works

`App.tsx` opens a `POST /stream` request and reads the response as a server-sent event stream. Three event types come back:

- `tool_start` — sets `activeTool` on the in-progress message so a per-tool status label renders (e.g. "Searching destinations…", "Building your itinerary…")
- `tool_end` — clears `activeTool` and appends the step to the reasoning panel
- `token` — appends the text chunk to the message content

While tokens are arriving the message renders a blinking cursor. Auto-scroll follows the stream but pauses if the user scrolls up, and resumes when the response finishes.

Session state is kept in `sessionStorage` (tab-isolated, cleared on page reload). Up to 40 messages of history are sent as context with each request. A warning banner appears at 36 messages and the input is disabled at 40 with a "Start new chat" prompt.

## Component overview

**`App.tsx`**  
Owns the message list, loading state, session ID, and scroll ref. Handles the SSE stream, `tool_start`/`tool_end`/`token` events, rate limit errors (429), and the session message cap.

**`MessageBubble.tsx`**  
Renders three states: user bubble (right-aligned), loading indicator (animated dots + per-tool status label after `tool_start`), and assistant message (full-width). Assistant text goes through a lightweight markdown renderer supporting `##`/`###` headings, `-`/`*` bullet lists, numbered lists, `**bold**`, and `[label](url)` links. A streaming cursor appends while the response is still arriving.

**`ReasoningPanel.tsx`**  
Collapsible panel below each assistant message. Lists every tool call as an expandable row with the raw JSON input and output.

**`ChatInput.tsx`**  
Textarea that auto-resizes up to 200px. Enter sends, Shift+Enter inserts a newline. Disabled while a response is in flight or the session cap is reached.

## Development

```bash
npm install
npm run dev
```

Runs on `http://localhost:5173`. Vite proxies `/stream`, `/plan`, `/health`, and `/usage` to `http://localhost:8000`, so no CORS config is needed during local development. The backend must be running first — see [server setup](../server/README.md).

### Environment variables

Create `.env.local` with a custom backend URL when pointing at a deployed backend instead of the local server:

```env
VITE_API_URL=https://your-app-runner-url.awsapprunner.com
```

Leave blank to use the Vite proxy during local development. Vite bakes env vars at build time, so a redeploy is required after changing this in Amplify.

## Deployment (AWS Amplify)

Build config lives in `amplify.yml` at the repo root. Amplify auto-deploys when `client/` changes on the `main` branch.

Required environment variable in the Amplify console:

| Variable | Value |
|---|---|
| `VITE_API_URL` | App Runner backend URL |

## Scripts

- `npm run dev` — dev server with hot reload
- `npm run build` — production build to `dist/`
- `npm run preview` — preview the production build locally
- `npm run lint` — run ESLint
