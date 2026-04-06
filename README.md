# Friction — The AI That Debates Your Idea Before Building the Plan

> "The AI that debates your idea, then builds the plan that survives the debate."

**Friction** is an AI deliberation engine powered by **GLM 5.1** that pressure-tests project ideas through structured multi-phase debate before generating implementation tickets. It replaces the "just start building" impulse with a rigorous thinking process — probing, challenging assumptions, running premortems — then produces a dependency-aware ticket DAG that coding agents can execute autonomously.

**Live Demo:** [https://zaihack.vercel.app](https://zaihack.vercel.app)

Built for the [Z.ai Builder Series](https://z.ai) hackathon (March 30 – April 6, 2026).

---

## The Problem: Task Delegation is Broken

Remember the Pied Piper problem from Silicon Valley? You have a brilliant idea, a team ready to build — but the moment you try to break it into tasks, everything falls apart. Tasks are vague, dependencies are missed, junior devs block senior devs, and half the team is building the wrong thing.

**This is the #1 failure mode in software.** Not bad code — bad planning.

Now multiply that by the age of AI agents. You can spin up 10 coding agents in parallel, but if you hand them vague tickets with tangled dependencies, you get 10 agents producing conflicting garbage. The bottleneck was never code generation — **it's task decomposition and delegation.**

Friction is the first system that **debates your idea before decomposing it**, then produces a dependency-aware DAG of self-contained tickets that agents (or humans) can execute in parallel without stepping on each other. Layer 0 tickets have zero dependencies. Layer 1 depends only on Layer 0. And so on. Every ticket is self-contained — no "see ticket #3" references, no implicit knowledge. An agent reading a single ticket knows exactly what to build, what files to touch, and what acceptance criteria to hit.

**This is the missing orchestration layer between "idea" and "agent swarm."**

---

## System Architecture

```mermaid
graph TB
    subgraph USER["User Input"]
        A["User Pitches Idea"]:::user
    end

    subgraph DELIBERATION["GLM 5.1 Deliberation Engine  (LangGraph State Machine)"]
        direction TB
        B["Phase 1: Probing"]:::phase
        C["Phase 2: Requirements Elicitation"]:::phase
        D["Phase 3: Cognitive Forcing"]:::phase
        E["Phase 4: Devil's Advocate"]:::phase
        F["Phase 5: Premortem Analysis"]:::phase
        G["Phase 6: Structured Summary"]:::phase

        B -->|"Sharp questions about<br/>differentiation & target user"| C
        C -->|"Scope, tech stack,<br/>integrations, constraints"| D
        D -->|"User rates confidence BEFORE<br/>seeing AI's assessment<br/>(prevents anchoring bias)"| E
        E -->|"Challenges assumptions with<br/>real competitor data via<br/>web search"| F
        F -->|"'It's 6 months later and<br/>this failed. Why?'"| G
    end

    subgraph SEARCH["Real-Time Intelligence"]
        S["DuckDuckGo Web Search"]:::search
        S2["Competitor Analysis"]:::search
        S3["Market Validation"]:::search
    end

    subgraph CODEBASE["Codebase Intelligence"]
        CB1["GitHub Repo Import"]:::codebase
        CB2["File Indexing &<br/>Language Detection"]:::codebase
        CB3["Architecture Pattern<br/>Recognition"]:::codebase
        CB4["Tech Stack Analysis"]:::codebase
    end

    subgraph OUTPUT["GLM 5.1 Structured Output"]
        H["Refined Idea +<br/>Risk Matrix"]:::output
        I["Ticket Generator"]:::output
        J["Dependency Graph<br/>Builder (DAG)"]:::output
    end

    subgraph TICKETS["Layered Ticket DAG"]
        direction LR
        L0["Layer 0<br/>Foundation"]:::layer0
        L1["Layer 1<br/>Core"]:::layer1
        L2["Layer 2<br/>Integration"]:::layer2
        L3["Layer 3<br/>Testing"]:::layer3
        L4["Layer 4<br/>Polish"]:::layer4

        L0 --> L1 --> L2 --> L3 --> L4
    end

    subgraph AGENTS["Agent Swarm (MCP Protocol)"]
        direction TB
        MCP["MCP Server<br/>(stdio transport)"]:::mcp
        AG1["Agent 1<br/>Backend"]:::agent
        AG2["Agent 2<br/>Frontend"]:::agent
        AG3["Agent 3<br/>Database"]:::agent
        AG4["Agent N<br/>..."]:::agent
    end

    subgraph LIFECYCLE["Ticket Lifecycle"]
        CL["Atomic Claim<br/>(lock-based)"]:::lifecycle
        EX["Agent Executes"]:::lifecycle
        RP["Output Summary +<br/>Bug Reports"]:::lifecycle
        PA["Bug-Aware Patching<br/>(downstream tickets<br/>auto-update)"]:::lifecycle

        CL --> EX --> RP --> PA
    end

    A --> B
    S -.->|"enriches"| E
    S2 -.->|"enriches"| E
    S3 -.->|"enriches"| B

    CB1 --> CB2 --> CB3 --> CB4
    CB4 -.->|"grounds tickets<br/>in real file paths"| I

    G --> H --> I --> J --> TICKETS

    MCP --> AG1 & AG2 & AG3 & AG4
    TICKETS -->|"get_next_ticket()"| MCP
    AG1 & AG2 & AG3 & AG4 -->|"mark_done(output)"| LIFECYCLE
    PA -.->|"patches downstream<br/>ticket descriptions"| TICKETS

    classDef user fill:#f59e0b,stroke:#d97706,color:#000,font-weight:bold
    classDef phase fill:#1e1e2e,stroke:#f59e0b,color:#f59e0b,font-weight:bold
    classDef search fill:#1e1e2e,stroke:#3b82f6,color:#3b82f6
    classDef codebase fill:#1e1e2e,stroke:#8b5cf6,color:#8b5cf6
    classDef output fill:#1e1e2e,stroke:#ef4444,color:#ef4444,font-weight:bold
    classDef layer0 fill:#059669,stroke:#047857,color:#fff,font-weight:bold
    classDef layer1 fill:#0284c7,stroke:#0369a1,color:#fff,font-weight:bold
    classDef layer2 fill:#7c3aed,stroke:#6d28d9,color:#fff,font-weight:bold
    classDef layer3 fill:#db2777,stroke:#be185d,color:#fff,font-weight:bold
    classDef layer4 fill:#dc2626,stroke:#b91c1c,color:#fff,font-weight:bold
    classDef mcp fill:#f59e0b,stroke:#d97706,color:#000,font-weight:bold
    classDef agent fill:#1e1e2e,stroke:#10b981,color:#10b981,font-weight:bold
    classDef lifecycle fill:#1e1e2e,stroke:#f97316,color:#f97316
```

### How Agent Delegation Works

```mermaid
sequenceDiagram
    participant U as User
    participant F as Friction Server
    participant GLM as GLM 5.1 (Z.ai)
    participant DB as SQLite
    participant A1 as Agent 1 (Backend)
    participant A2 as Agent 2 (Frontend)
    participant A3 as Agent 3 (Testing)

    U->>F: POST /api/sessions/ {idea}
    F->>GLM: Deliberation Phase 1-6 (12+ LLM calls)
    GLM-->>F: Probing → Requirements → Cognitive Forcing → Challenge → Premortem → Summary

    U->>F: POST /sessions/{id}/complete
    F->>GLM: Generate structured ticket JSON
    GLM-->>F: 5-12 tickets with dependency DAG
    F->>DB: Store tickets + dependency graph

    Note over A1,A3: Agents connect via MCP (stdio) or HTTP

    par Layer 0 — All agents can claim simultaneously
        A1->>F: get_next_ticket()
        F->>DB: Atomic claim (lock-based)
        F-->>A1: FRIC-001 "Setup project structure"
        A2->>F: get_next_ticket()
        F-->>A2: FRIC-002 "Design database schema"
    end

    A1->>F: mark_done({output_summary, files_created})
    F->>DB: Complete ticket + unlock dependents

    Note over F: Bug-aware patching: if A1 reports issues,<br/>GLM 5.1 auto-patches downstream tickets

    par Layer 1 — Unlocked after Layer 0 completes
        A1->>F: get_next_ticket()
        F-->>A1: FRIC-003 "Implement API endpoints"
        A2->>F: get_next_ticket()
        F-->>A2: FRIC-004 "Build React components"
        A3->>F: get_next_ticket()
        F-->>A3: FRIC-005 "Write integration tests"
    end

    Note over A1,A3: Each ticket is self-contained.<br/>No "see ticket #3" references.<br/>No implicit knowledge. No conflicts.
```

---

## What It Does & Who It's For

**For solo developers** who start building before thinking and end up rebuilding. **For teams running agent swarms** who need structured task delegation without conflicts. **For hackathon teams** who need to rapidly validate ideas and split work. **For engineering managers** who want structured ideation before sprint planning.

### The 6-Phase Deliberation

| Phase | What Happens | Why It Matters |
|-------|-------------|----------------|
| **Probing** | Sharp questions about differentiation, target user, scope | Kills vague ideas early |
| **Requirements** | Concrete scope, tech stack, integrations, constraints | Forces specificity |
| **Cognitive Forcing** | User rates confidence BEFORE seeing AI's scores | Prevents anchoring bias |
| **Devil's Advocate** | Challenges assumptions with real competitor data (web search) | Grounds ideas in reality |
| **Premortem** | "It's 6 months later and this failed. Why?" | Surfaces hidden risks |
| **Summary** | Structured JSON: refined idea, risks, scope, confidence delta | Machine-readable output |

---

## How GLM 5.1 Is Used (and Why)

Friction is a **long-horizon, multi-step reasoning system** — exactly the kind of workload GLM 5.1 excels at. It's not a single API call; every session makes **12+ sequential LLM calls** across 6 deliberation phases, each building on the full conversation context.

**Multi-phase deliberation**: Each session runs through probing → requirements → cognitive forcing → devil's advocate → premortem → summary. GLM 5.1's strong agentic reasoning handles the nuanced back-and-forth where the AI must remember context across phases, adjust its stance when the user makes strong arguments, and maintain coherent challenge throughout.

**Structured output generation**: After deliberation, GLM 5.1 generates complex JSON containing refined ideas, categorized risks with severity/mitigation, recommended scope, tech stack suggestions, and confidence deltas — then a second call generates 5-12 layered tickets with dependency graphs. The model's instruction-following ensures clean, parseable JSON output consistently.

**Tool use / Agent behavior via MCP**: The MCP server exposes Friction as a tool suite for coding agents. Agents call `get_next_ticket` → implement → `mark_done` in a fully agentic workflow. GLM 5.1's tool-use capabilities make it reliable for generating the structured ticket data that downstream agents consume.

**Bug-aware ticket patching**: When a completed ticket reports issues, GLM 5.1 analyzes upstream bug reports and patches downstream ticket descriptions with context-aware warnings — a multi-step reasoning task requiring understanding of dependency chains.

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
| Web Search | DuckDuckGo (grounding deliberation in real competitor data) |
| Deployment | Vercel (Fluid Compute for Python) |

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/sessions/` | Create session, start deliberation |
| `POST` | `/api/sessions/{id}/message` | Chat with Friction |
| `POST` | `/api/sessions/{id}/complete` | End deliberation, generate tickets |
| `POST` | `/api/sessions/{id}/tickets/next` | Atomic claim next ticket (lock-based) |
| `PATCH` | `/api/tickets/{id}` | Update ticket (complete/fail + output) |
| `GET` | `/api/sessions/{id}/workflow` | Dependency graph (DAG) |
| `WS` | `/ws` | Real-time events (ticket claims, completions) |

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
    graph.py             # LangGraph state machine (6-phase flow)
    nodes.py             # Phase node functions (probe, challenge, etc.)
    prompts.py           # System prompts for each deliberation phase
    state.py             # Deliberation state schema
  tickets/
    generator.py         # LLM-powered ticket generation (layered DAG)
    manager.py           # Ticket lifecycle + bug-aware patching
    dependency_graph.py  # DAG builder + topological ordering
  codebase/
    importer.py          # Git clone + directory walker
    analyzer.py          # LLM-powered codebase analysis
    indexer.py           # File indexing + language detection
    github_issues.py     # GitHub issue fetcher
    issue_ticket_generator.py  # Convert issues → tickets
  mcp_server/
    server.py            # MCP stdio server for agent integration
  routers/               # FastAPI route handlers
  models/                # Pydantic models
frontend/
  src/
    components/          # React components (chat, ticket board, DAG viz)
    store/               # Zustand state management
    lib/                 # API client, utilities
```

---

## Why This Matters

Every AI coding tool today focuses on **generating code faster**. None of them ask: *should this code exist?*

Friction is the layer that sits between your idea and your agent swarm. It's the architect that refuses to let you build on a shaky foundation. It's the senior engineer who asks "have you considered..." before you've written a single line.

The result: when your agents start building, they're building the **right thing**, in the **right order**, with **zero coordination overhead**.

---

## License

MIT

---

Built with GLM 5.1 by [Kevin](https://github.com/Kvndoshi) for the Z.ai Builder Series hackathon.

#buildwithglm
