"""Codebase import, analysis, GitHub issues, and issue-ticket generation."""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.codebase.indexer import CodebaseIndexer
from backend.models.codebase import CodebaseAnalysis, GitHubIssue, parse_github_owner_repo
from backend.models.events import EventType, WSEvent
from backend.services.db import (
    get_codebase_analysis,
    get_github_issues,
    get_github_issues_by_ids,
    get_session,
    save_codebase_analysis,
    save_github_issues,
    update_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/codebase", tags=["codebase"])


class ImportRequest(BaseModel):
    repo_url: str
    session_id: Optional[str] = None


class ImportResponse(BaseModel):
    analysis: CodebaseAnalysis
    issues: list[GitHubIssue] = []


class GenerateIssueTicketsRequest(BaseModel):
    issue_ids: list[str]
    session_id: str


@router.post("/import")
async def import_codebase(body: ImportRequest, request: Request):
    """Clone a git repo, analyze it, fetch GitHub issues, and return results."""
    importer = request.app.state.importer
    analyzer = request.app.state.analyzer
    issues_fetcher = request.app.state.issues_fetcher

    try:
        clone_path, files = await importer.import_from_git(body.repo_url)

        # Parse GitHub owner/repo for issue fetching
        gh_info = parse_github_owner_repo(body.repo_url)

        # Run analysis and issue fetching in parallel
        if gh_info:
            analysis_coro = analyzer.analyze(
                files=files, repo_url=body.repo_url,
                session_id=body.session_id, root_dir=clone_path,
            )
            issues_coro = issues_fetcher.fetch_issues(gh_info[0], gh_info[1])
            analysis, issues = await asyncio.gather(analysis_coro, issues_coro)
        else:
            analysis = await analyzer.analyze(
                files=files, repo_url=body.repo_url,
                session_id=body.session_id, root_dir=clone_path,
            )
            issues = []

        # Generate codebase index/map while files are still on disk
        try:
            indexer = CodebaseIndexer()
            analysis.codebase_index = indexer.generate_index(clone_path, analysis)
        except Exception:
            logger.exception("Codebase index generation failed; continuing without index")

        # Save analysis
        await save_codebase_analysis(analysis)

        # Link analysis to session
        if body.session_id:
            session = await get_session(body.session_id)
            if session:
                session.codebase_id = analysis.id
                await update_session(session)

        # Save issues
        if issues:
            await save_github_issues(analysis.id, issues)

        return {
            "analysis": analysis.model_dump(mode="json"),
            "issues": [i.model_dump(mode="json") for i in issues],
        }
    except Exception as e:
        logger.exception("Codebase import failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_codebase():
    """Placeholder for file upload endpoint."""
    return {"message": "File upload not yet implemented. Use /import with a git URL."}


@router.get("/{analysis_id}", response_model=CodebaseAnalysis)
async def get_analysis(analysis_id: str):
    """Return a previously computed codebase analysis."""
    analysis = await get_codebase_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.get("/{analysis_id}/index")
async def get_codebase_index(analysis_id: str):
    """Return the codebase index/map for an analysis."""
    analysis = await get_codebase_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"index": analysis.codebase_index}


@router.get("/{analysis_id}/issues", response_model=list[GitHubIssue])
async def get_issues(analysis_id: str):
    """Return all saved GitHub issues for an analysis."""
    return await get_github_issues(analysis_id)


@router.post("/{analysis_id}/generate-tickets")
async def generate_tickets_from_issues(
    analysis_id: str,
    body: GenerateIssueTicketsRequest,
    request: Request,
):
    """Generate implementation tickets from selected GitHub issues."""
    manager = request.app.state.manager
    ws_manager = request.app.state.ws_manager
    generator = request.app.state.issue_ticket_generator

    analysis = await get_codebase_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")

    issues = await get_github_issues_by_ids(body.issue_ids)
    if not issues:
        raise HTTPException(status_code=400, detail="No issues found for given IDs")

    try:
        tickets = await generator.generate_from_issues(
            issues=issues,
            codebase=analysis,
            session_id=body.session_id,
        )

        created = await manager.create_tickets(body.session_id, tickets)

        # Generate/update agent prompt
        session = await get_session(body.session_id)
        if session:
            from backend.tickets.prompt_generator import generate_agent_prompt
            session.agent_prompt = generate_agent_prompt(session, created, analysis)
            await update_session(session)

        await ws_manager.broadcast(
            WSEvent(
                type=EventType.ISSUE_TICKETS_GENERATED,
                session_id=body.session_id,
                data={
                    "analysis_id": analysis_id,
                    "ticket_count": len(created),
                    "issue_count": len(issues),
                },
            )
        )

        return [t.model_dump(mode="json") for t in created]
    except Exception as e:
        logger.exception("Failed to generate tickets from issues")
        raise HTTPException(status_code=500, detail=str(e))
