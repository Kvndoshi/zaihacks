"""Web search service using Tavily API.

Provides a simple async search function used by the deliberation engine
to ground its responses in real-world data when relevant.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword heuristics — decide whether a search is worthwhile
# ---------------------------------------------------------------------------

_SEARCH_TRIGGER_PATTERNS: list[re.Pattern[str]] = [
    # User asks about specific tools/frameworks
    re.compile(r"\b(should i use|what about|have you heard of|is .+ good)\b", re.I),
    re.compile(r"\b(vs\.?|versus|compared to|alternative to|better than)\b", re.I),
    # Tech / product names (capitalized words or known patterns)
    re.compile(r"\b(react|vue|angular|svelte|next\.?js|nuxt|django|flask|fastapi|express|rails|spring|laravel)\b", re.I),
    re.compile(r"\b(supabase|firebase|aws|gcp|azure|vercel|netlify|heroku|docker|kubernetes)\b", re.I),
    re.compile(r"\b(stripe|twilio|sendgrid|auth0|clerk|openai|anthropic|gemini|langchain|llamaindex)\b", re.I),
    re.compile(r"\b(postgres|mysql|mongodb|redis|sqlite|dynamodb|cockroachdb|planetscale)\b", re.I),
    # Market / competitor questions
    re.compile(r"\b(competitor|competitors|market|pricing|existing solution|already exists)\b", re.I),
    re.compile(r"\b(how much does|what does .+ cost|free tier|open source alternative)\b", re.I),
]

# Phases where search is especially useful
_SEARCH_FRIENDLY_PHASES = {"probing", "challenge", "requirements"}


def should_search(
    user_message: str,
    phase: str,
    idea: str = "",
) -> bool:
    """Decide whether a web search would add value for this turn.

    Uses cheap keyword heuristics — no LLM call.
    """
    text = f"{user_message} {idea}"

    # Check trigger patterns
    for pattern in _SEARCH_TRIGGER_PATTERNS:
        if pattern.search(text):
            return True

    # In probing/challenge phases, search if the idea mentions a product category
    if phase in _SEARCH_FRIENDLY_PHASES and len(user_message.split()) > 3:
        # Look for proper nouns (rough heuristic: capitalized words not at start of sentence)
        words = user_message.split()
        proper_nouns = [
            w for w in words[1:]
            if w[0].isupper() and len(w) > 2 and not w.isupper()
        ]
        if proper_nouns:
            return True

    return False


def build_search_query(user_message: str, idea: str, phase: str) -> str:
    """Construct a focused search query from the conversation context."""
    if phase == "challenge":
        return f"{idea} competitors alternatives"
    if phase == "requirements":
        return f"{idea} tech stack tools"

    # Default: use the user's message, trimmed
    query = user_message.strip()
    if len(query) > 120:
        query = query[:120]
    return query


# ---------------------------------------------------------------------------
# Search function — Tavily API
# ---------------------------------------------------------------------------

async def web_search(query: str, num_results: int = 5) -> list[dict[str, Any]]:
    """Search the web using Tavily and return results.

    Each result dict has keys: title, content (snippet), url.
    Returns an empty list on any error so the caller can proceed without search.

    Requires TAVILY_API_KEY in environment or .env file.
    """
    api_key = os.getenv("TAVILY_API_KEY", "")
    if not api_key:
        logger.warning("TAVILY_API_KEY not set — skipping web search")
        return []

    try:
        import aiohttp
    except ImportError:
        logger.warning("aiohttp not installed — skipping web search")
        return []

    try:
        async with aiohttp.ClientSession() as session:
            resp = await session.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": api_key,
                    "query": query,
                    "max_results": num_results,
                    "search_depth": "basic",
                    "include_answer": False,
                },
                timeout=aiohttp.ClientTimeout(total=10),
            )
            resp.raise_for_status()
            data = await resp.json()

        results = data.get("results", [])
        logger.info("Tavily search for %r returned %d results", query, len(results))
        return results
    except Exception as exc:
        logger.warning("Tavily search failed for %r: %s", query, exc)
        return []


def format_search_results(results: list[dict[str, Any]]) -> str:
    """Format search results into a string suitable for prompt injection."""
    if not results:
        return ""

    lines = ["Web search results (use if relevant, ignore if not):"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "")
        snippet = r.get("content", r.get("body", ""))
        url = r.get("url", r.get("href", ""))
        lines.append(f"{i}. [{title}] - {snippet} ({url})")

    return "\n".join(lines)
