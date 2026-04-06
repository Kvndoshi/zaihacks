# Friction — The AI That Debates Your Idea Before Building the Plan

> "The AI that debates your idea, then builds the plan that survives the debate."

**Friction** is an AI deliberation engine powered by **GLM 5.1** that pressure-tests project ideas through structured multi-phase debate before generating implementation tickets. It replaces the "just start building" impulse with a rigorous thinking process — probing, challenging assumptions, running premortems — then produces a dependency-aware ticket DAG that coding agents can execute autonomously.

**Live Demo:** [https://zaihack.vercel.app](https://zaihack.vercel.app)

Built for the [Z.ai Builder Series](https://z.ai) hackathon (March 30 – April 6, 2026).

---

## What It Does & Who It's For

Friction solves the #1 failure mode of software projects: **building the wrong thing**. Most developers jump straight from idea to code. Friction forces a structured debate first.

**For solo developers** who start building before thinking and end up rebuilding. **For hackathon teams** who need to rapidly validate ideas and split work. **For AI agent users** who want their coding agents to work from well-reasoned tickets instead of vague prompts.

### The Flow

1. You pitch an idea → Friction **probes** with sharp questions
2. It elicits **requirements** and **forces you to rate your confidence** before revealing its own assessment
3. It plays **devil's advocate**, citing real competitors via web search
4. It runs a **premortem** — "It's 6 months later and this failed. Why?"
5. It generates a **structured summary** with refined idea, risks, and scope
6. It produces **5-12 layered tickets** with a dependency DAG
7. Coding agents (Cursor, Claude Code) consume tickets via **MCP** and build autonomously

---

## How GLM 5.1 Is Used (and Why)

Friction is a **long-horizon, multi-step reasoning system** — exactly the kind of workload GLM 5.1 excels at. It's not a single API call; every session makes **12+ sequential LLM calls** across 6 deliberation phases, each building on the full conversation context.

**Multi-phase deliberation**: Each session runs through probing → requirements → cognitive forcing → devil's advocate → premortem → summary. GLM 5.1's strong agentic reasoning handles the nuanced back-and-forth where the AI must remember context across phases, adjust its stance when the user makes strong arguments, and maintain coherent challenge throughout.

**Structured output generation**: After deliberation, GLM 5.1 generates complex JSON containing refined ideas, categorized risks with severity/mitigation, recommended scope, tech stack suggestions, and confidence deltas — then a second call generates 5-12 layered tickets with dependency graphs. The model's instruction-following ensures clean, parseable JSON output consistently.

**Tool use / Agent behavior via MCP**: The MCP server exposes Friction as a tool suite for coding agents. Agents call `get_next_ticket` → implement → `mark_done` in a fully agentic workflow. GLM 5.1's tool-use capabilities make it reliable for generating the structured ticket data that downstream agents consume.

**Bug-aware ticket patching**: When a completed ticket reports issues, GLM 5.1 analyzes upstream bug reports and patches downstream ticket descriptions with context-aware warnings — a multi-step reasoning task requiring understanding of dependency chains.

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

### Deliberation Flow (6 Phases)

```
 Idea → [Probing] → [Requirements] → [Cognitive Forcing] → [Challenge] → [Premortem] → [Summary]
                                                                                           |
                                                                                    Ticket Generation
                                                                                           |
                                                                              [5-12 Layered Tickets]
                                                                                           |
                                                                                  Dependency DAG
                                                                                           |
                                                                              Agent executes via MCP
```

---

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Z.ai API key ([get one here](https://z.ai))

### Backend
```bash
cd backend
cp .env.template .env
# Edit .env → add your ZAI_API_KEY
pip install -e ..    # installs from pyproject.toml
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
| Web Search | DuckDuckGo (for grounding deliberation in real competitor data) |
| Deployment | Vercel (Fluid Compute for Python) |

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
