# Friction — AI Deliberation Server + Ticket Orchestrator

DevLabs Hackathon (March 19, 2026). Track 2: "Designing AI that improves judgment, not just productivity."

## One-liner
"The AI that debates your idea, then builds the plan that survives the debate."

## Quick Start

### Backend
```bash
cd devlabs_hackathon/backend
cp .env.template .env  # Add your ZAI_API_KEY
pip install -r requirements.txt
cd .. && python -m backend.run
# Server starts on http://localhost:8080
```

### Frontend
```bash
cd devlabs_hackathon/frontend
npm install
npm run dev
# Opens on http://localhost:5173
```

### MCP Server (for agent integration)
```bash
cd devlabs_hackathon
python -m backend.mcp_server
```

## Architecture
- **Backend**: FastAPI + LangGraph + GLM 5.1 (Z.ai) + aiosqlite
- **Frontend**: React 18 + Vite + TypeScript + ReactFlow + Zustand + Tailwind
- **Database**: SQLite with JSON columns
- **LLM**: GLM 5.1 via Z.ai OpenAI-compatible API (openai SDK)
- **Theme**: Dark + Amber (#f59e0b primary, #ef4444 accent, #0f0f0f bg)

## Key Concepts
- **Deliberation**: Multi-phase AI debate (probing → cognitive forcing → challenge → premortem → summary)
- **Cognitive Forcing**: User rates confidence BEFORE seeing AI's assessment
- **Tickets**: Self-contained, layered with dependency DAG
- **Bug-aware**: Later tickets auto-patch based on earlier ticket output bugs
- **MCP**: Agents call get_next_ticket/mark_done via stdio transport

## API Endpoints
- `POST /api/sessions/` — Create session, start deliberation
- `POST /api/sessions/{id}/message` — Chat with Friction
- `POST /api/sessions/{id}/complete` — End deliberation, generate tickets
- `POST /api/sessions/{id}/tickets/next` — Get & claim next ticket
- `PATCH /api/tickets/{id}` — Update ticket (complete/fail)
- `GET /api/sessions/{id}/workflow` — Dependency graph
- `WS /ws` — Real-time events

## Convention
- Pydantic v2 (`model_dump()`, `model_validate()`)
- Backend imports use `backend.` prefix
- All DB ops are async via aiosqlite
