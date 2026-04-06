"""Claude Code prehook — intercepts prompts and routes through Friction deliberation.

Reads from stdin, checks if the user message should trigger deliberation.
If so, blocks and redirects to Friction dashboard.
"""

from __future__ import annotations

import json
import sys

TRIGGER_PREFIXES = [
    "build", "create", "implement", "make", "write", "develop",
    "design", "add", "set up", "scaffold", "generate",
]


def handle_prehook() -> None:
    """Read Claude Code prehook input, optionally route through Friction."""
    try:
        input_data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError):
        print(json.dumps({"action": "passthrough"}))
        return

    user_message = input_data.get("message", "")
    lower = user_message.lower().strip()

    should_intercept = any(lower.startswith(p) for p in TRIGGER_PREFIXES)

    if should_intercept:
        output = {
            "action": "block",
            "message": (
                "FRICTION: Before I build this, let's think it through.\n\n"
                "Your request has been intercepted by Friction — the AI that "
                "debates your idea before building it.\n\n"
                "Open the Friction dashboard at http://localhost:5173 to "
                "complete the deliberation process, or respond here to continue.\n\n"
                "Why? Research shows AI degrades human judgment when it says 'yes' "
                "immediately. Friction challenges your assumptions first, then "
                "generates better implementation plans."
            ),
        }
    else:
        output = {"action": "passthrough"}

    print(json.dumps(output))


if __name__ == "__main__":
    handle_prehook()
