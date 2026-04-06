"""
End-to-end test: creates a deliberation, chats, completes, verifies tickets.

    python test_e2e.py

Runs against the app directly via httpx ASGI transport with lifespan.
"""

import asyncio
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv("backend/.env")


async def run_test():
    from httpx import AsyncClient, ASGITransport
    from backend.main import app

    transport = ASGITransport(app=app)

    # Manually trigger lifespan startup
    from backend.services.db import init_db
    from backend.services.llm import LLMClient
    from backend.deliberation.engine import DeliberationEngine
    from backend.tickets.generator import TicketGenerator
    from backend.tickets.manager import TicketManager
    from backend.services.websocket_manager import ConnectionManager
    from backend.codebase.importer import CodebaseImporter
    from backend.codebase.analyzer import CodebaseAnalyzer

    await init_db()
    llm = LLMClient()
    app.state.llm = llm
    app.state.engine = DeliberationEngine(llm)
    app.state.generator = TicketGenerator(llm)
    app.state.manager = TicketManager(llm)
    app.state.ws_manager = ConnectionManager()
    app.state.importer = CodebaseImporter()
    app.state.analyzer = CodebaseAnalyzer(llm)

    async with AsyncClient(transport=transport, base_url="http://test", timeout=120) as c:

        print("=" * 60)
        print("FRICTION E2E TEST")
        print("=" * 60)

        # 1. Health check
        r = await c.get("/api/health")
        assert r.status_code == 200, f"Health failed: {r.status_code}"
        print(f"\n[PASS] Health check: {r.json()}")

        # 2. Create session
        print("\n--- Creating session: 'Build a calculator app' ---")
        r = await c.post("/api/sessions/", json={"idea": "Build a calculator app that can do basic math operations"})
        assert r.status_code == 200, f"Create session failed: {r.status_code} {r.text}"
        session = r.json()
        session_id = session["id"]
        print(f"[PASS] Session created: {session_id}")
        print(f"  Title: {session['title']}")
        print(f"  Status: {session['status']}")
        print(f"  Messages: {len(session['messages'])}")
        if session["messages"]:
            friction_msg = session["messages"][-1]["content"]
            print(f"  Friction says: {friction_msg[:300]}...")

        # 3. Send a user message
        print("\n--- Sending user reply ---")
        r = await c.post(f"/api/sessions/{session_id}/message", json={
            "content": "It should be a web-based calculator with basic operations (+, -, *, /). Simple UI, nothing fancy. I want to build it in a day."
        })
        assert r.status_code == 200, f"Send message failed: {r.status_code} {r.text}"
        ai_msg = r.json()
        print(f"[PASS] AI responded (phase: {ai_msg.get('phase', '?')})")
        print(f"  Content: {ai_msg['content'][:300]}...")

        # 4. Send another message
        print("\n--- Sending second reply ---")
        r = await c.post(f"/api/sessions/{session_id}/message", json={
            "content": "Good points. I'll use React for frontend and keep it client-side only. No backend needed. Target audience is students."
        })
        assert r.status_code == 200, f"Second message failed: {r.status_code} {r.text}"
        ai_msg2 = r.json()
        print(f"[PASS] AI responded (phase: {ai_msg2.get('phase', '?')})")
        print(f"  Content: {ai_msg2['content'][:300]}...")

        # 5. Complete deliberation and generate tickets
        print("\n--- Completing deliberation + generating tickets ---")
        r = await c.post(f"/api/sessions/{session_id}/complete")
        assert r.status_code == 200, f"Complete failed: {r.status_code} {r.text}"
        completed = r.json()
        print(f"[PASS] Deliberation completed")
        print(f"  Status: {completed['status']}")
        print(f"  Refined idea: {(completed.get('refined_idea') or 'N/A')[:200]}")
        print(f"  Key insights: {completed.get('key_insights', [])[:3]}")
        print(f"  Risks: {completed.get('risks', [])[:3]}")

        # 6. Get tickets
        print("\n--- Fetching tickets ---")
        r = await c.get(f"/api/sessions/{session_id}/tickets")
        assert r.status_code == 200, f"Get tickets failed: {r.status_code} {r.text}"
        tickets = r.json()
        print(f"[PASS] Got {len(tickets)} tickets")
        for t in tickets:
            deps = ", ".join(t["depends_on"]) if t["depends_on"] else "none"
            print(f"  {t['id']} | L{t['layer']} | {t['status']:12} | {t['domain']:10} | {t['title'][:50]} | deps: {deps}")

        # 7. Get workflow
        print("\n--- Fetching workflow graph ---")
        r = await c.get(f"/api/sessions/{session_id}/workflow")
        assert r.status_code == 200, f"Get workflow failed: {r.status_code} {r.text}"
        workflow = r.json()
        print(f"[PASS] Workflow: {len(workflow['nodes'])} nodes, {len(workflow['edges'])} edges")

        # 8. Get next ticket (simulate agent)
        print("\n--- Simulating agent: get_next_ticket ---")
        r = await c.post(f"/api/sessions/{session_id}/tickets/next", json={})
        if r.status_code == 200:
            result = r.json()
            ticket = result["ticket"]
            print(f"[PASS] Agent got ticket: {ticket['id']} - {ticket['title']}")
            print(f"  Dependency outputs: {list(result['dependency_outputs'].keys())}")

            # 9. Complete the ticket
            print(f"\n--- Marking {ticket['id']} as done ---")
            r = await c.patch(f"/api/tickets/{ticket['id']}", json={
                "status": "completed",
                "output_summary": "Built the calculator component. Files: src/Calculator.tsx. Known issue: division by zero not handled."
            })
            assert r.status_code == 200, f"Complete ticket failed: {r.status_code} {r.text}"
            print(f"[PASS] Ticket {ticket['id']} marked complete")
        elif r.status_code == 404:
            print(f"[WARN] No tickets available")

        # 10. Board status
        print("\n--- Board status ---")
        r = await c.get(f"/api/sessions/{session_id}/status")
        assert r.status_code == 200, f"Status failed: {r.status_code} {r.text}"
        stats = r.json()
        print(f"[PASS] Board: {stats.get('completed', 0)}/{stats.get('total', 0)} complete, "
              f"{stats.get('ready', 0)} ready, {stats.get('blocked', 0)} blocked")

        # 11. List sessions
        print("\n--- Listing all sessions ---")
        r = await c.get("/api/sessions/")
        assert r.status_code == 200
        sessions_list = r.json()
        print(f"[PASS] {len(sessions_list)} session(s) in database")

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_test())
