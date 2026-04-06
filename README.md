# Friction — The AI That Debates Your Idea Before Building the Plan

> "The AI that debates your idea, then builds the plan that survives the debate."

**Friction** is an AI deliberation engine powered by **GLM 5.1** that pressure-tests project ideas through structured multi-phase debate before generating implementation tickets. It replaces the "just start building" impulse with a rigorous thinking process — probing, challenging assumptions, running premortems — then produces a dependency-aware ticket DAG that agents can execute.

Built for the [Z.ai Builder Series](https://z.ai) hackathon (March 30 - April 6, 2026).

---

## Why GLM 5.1?

Friction is a **long-horizon, multi-step reasoning system** — exactly the kind of workload GLM 5.1 excels at:

1. **Multi-phase deliberation (6 phases, 12+ LLM calls per session)**: Each deliberation runs through probing, requirements elicitation, cognitive forcing, devil's advocate challenge, premortem analysis, and structured summarization. GLM 5.1's strong agentic reasoning (85.0 avg on agent leaderboard) handles the nuanced back-and-forth where the AI must remember context, adjust its stance when the user makes strong arguments, and maintain coherent challenge across phases.

2. **Structured output generation**: After deliberation, GLM 5.1 generates a complex JSON structure containing refined ideas, categorized risks with severity/mitigation, recommended scope, tech stack suggestions, and confidence deltas. The model's instruction-following ensures clean, parseable JSON output consistently.

3. **Tool use / Agent behavior via MCP**: The MCP server exposes Friction as a tool suite for coding agents (Cursor, Claude Code, etc.). Agents call `start_deliberation` → debate in the browser → `get_agent_prompt` → `get_next_ticket` → `mark_done` in a fully agentic workflow. GLM 5.1's tool-use capabilities make it reliable for generating the structured ticket data that downstream agents consume.

4. **Bug-aware ticket patching**: When a completed ticket reports issues, GLM 5.1 analyzes the upstream bug reports and patches downstream ticket descriptions with context-aware warnings — a multi-step reasoning task that requires understanding dependency chains and synthesizing failure information.

---

## Architecture

```
                                    +------------------+
                                    |   React + Vite   |
                                    |   Frontend UI    |
                                    | (ReactFlow DAG)  |
                                    +--------+---------+
                                             |
                                        HTTP / WS
                                             |
+------------------+              +----------v----------+
|   Coding Agent   |  MCP stdio   |    FastAPI Server    |
| (Cursor / Claude |<------------>|                      |
|    Code / etc)   |              |  +----------------+  |
+------------------+              |  | Deliberation   |  |
                                  |  | Engine         |  |
                                  |  | (LangGraph)    |  |
                                  |  +-------+--------+  |
                                  |          |           |
                                  |  +-------v--------+  |
                                  |  | Ticket         |  |
                                  |  | Orchestrator   |  |
                                  |  | (DAG + claims) |  |
                                  |  +-------+--------+  |
                                  |          |           |
                                  +----------+-----------+
                                             |
                                    +--------v---------+
                                    |   GLM 5.1 API    |
                                    |   (Z.ai)         |
                                    +------------------+
                                             |
                                    +--------v---------+
                                    |  SQLite + JSON   |
                                    |  (aiosqlite)     |
                                    +------------------+
```

### System Flow

1. **User pitches idea** via the React dashboard or MCP tool
2. **Deliberation Engine** (LangGraph state machine) runs 6 phases:
   - **Probing** — Sharp questions about differentiation, target user, scope
   - **Requirements** — Concrete scope, tech stack, integrations
   - **Cognitive Forcing** — User rates confidence BEFORE seeing AI's scores (prevents anchoring bias)
   - **Challenge** — Devil's advocate with real competitor data (web search enriched)
   - **Premortem** — "It's 6 months later and this failed. Why?"
   - **Summary** — Structured JSON: refined idea, risks, scope, confidence delta
3. **Ticket Generation** — GLM 5.1 produces 5-12 layered tickets with dependency DAG
4. **Ticket Orchestration** — Agents claim tickets atomically, complete with output summaries
5. **Bug-aware patching** — Downstream tickets auto-patch based on upstream bug reports

### Key Design Decisions

- **Single LLM abstraction** (`backend/services/llm.py`): All GLM 5.1 calls go through one client — chat, structured output, and streaming
- **LangGraph for deliberation flow**: State machine with conditional routing ensures phases progress correctly
- **Atomic ticket claiming**: Lock-based concurrency prevents two agents from grabbing the same ticket
- **Self-contained tickets**: Every ticket includes full context — no "see ticket X" references

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- Z.ai API key with GLM Coding Plan

### Backend
```bash
cd backend
cp .env.template .env
# Edit .env and add your ZAI_API_KEY
pip install -r requirements.txt
cd .. && python -m backend.run
# Server starts on http://localhost:8080
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# Opens on http://localhost:5173
```

### MCP Server (for agent integration)
```bash
python -m backend.mcp_server
```

Add to your agent's MCP config:
```json
{
  "mcpServers": {
    "friction": {
      "command": "python",
      "args": ["-m", "backend.mcp_server"],
      "cwd": "/path/to/this/repo"
    }
  }
}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| LLM | **GLM 5.1** via Z.ai OpenAI-compatible API |
| Backend | FastAPI, LangGraph, aiosqlite |
| Frontend | React 18, Vite, TypeScript, ReactFlow, Zustand, Tailwind CSS |
| Database | SQLite with JSON columns |
| Agent Protocol | MCP (Model Context Protocol) via stdio |
| Web Search | DuckDuckGo (for grounding deliberation in real data) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/sessions/` | Create session, start deliberation |
| POST | `/api/sessions/{id}/message` | Chat with Friction |
| POST | `/api/sessions/{id}/complete` | End deliberation, generate tickets |
| POST | `/api/sessions/{id}/tickets/next` | Get & claim next ticket |
| PATCH | `/api/tickets/{id}` | Update ticket (complete/fail) |
| GET | `/api/sessions/{id}/workflow` | Dependency graph |
| WS | `/ws` | Real-time events |

---

## Who Is This For?

- **Solo developers** who start building before thinking and end up rebuilding
- **Hackathon teams** who need to rapidly validate ideas and split work
- **Engineering managers** who want structured ideation before sprint planning
- **AI agent users** who want their coding agents to work from well-reasoned tickets instead of vague prompts

---

## Project Structure

```
backend/
  config.py              # Environment config (Z.ai API key, model)
  main.py                # FastAPI app with WebSocket + SPA serving
  services/
    llm.py               # GLM 5.1 client (OpenAI-compatible)
    db.py                # Async SQLite operations
    web_search.py        # Web search for grounding deliberation
  deliberation/
    engine.py            # Session orchestrator
    graph.py             # LangGraph state machine
    nodes.py             # Phase node functions (probe, challenge, etc.)
    prompts.py           # System prompts for each phase
    state.py             # Deliberation state schema
  tickets/
    generator.py         # LLM-powered ticket generation
    manager.py           # Ticket lifecycle + bug-aware patching
    dependency_graph.py  # DAG builder
  mcp_server/
    server.py            # MCP stdio server for agent integration
  routers/               # FastAPI route handlers
  models/                # Pydantic models
frontend/
  src/
    components/          # React components (chat, board, workflow graph)
    store/               # Zustand state management
    lib/                 # API client, utilities
```

---

## License

MIT

---

Built with GLM 5.1 by [Kevin](https://github.com/Kvndoshi) for the Z.ai Builder Series hackathon.

#buildwithglm
