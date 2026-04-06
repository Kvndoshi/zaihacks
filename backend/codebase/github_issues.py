"""Fetch open issues from a public GitHub repository."""

from __future__ import annotations

import logging

import aiohttp

from backend.models.codebase import GitHubIssue, GitHubLabel, IssueType

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com/repos"


class GitHubIssuesFetcher:
    """Scrape open issues from a public GitHub repo (no auth required)."""

    async def fetch_issues(self, owner: str, repo: str) -> list[GitHubIssue]:
        url = f"{_GITHUB_API}/{owner}/{repo}/issues?state=open&per_page=100"
        headers = {
            "User-Agent": "Friction/0.1",
            "Accept": "application/vnd.github.v3+json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        logger.warning("GitHub API returned %d for %s/%s", resp.status, owner, repo)
                        return []
                    data = await resp.json()
        except Exception:
            logger.exception("Failed to fetch GitHub issues for %s/%s", owner, repo)
            return []

        issues: list[GitHubIssue] = []
        for item in data:
            # Skip pull requests (they also appear in /issues)
            if "pull_request" in item:
                continue

            labels = [
                GitHubLabel(name=lbl["name"], color=lbl.get("color", ""))
                for lbl in item.get("labels", [])
            ]

            issue_type = self._classify_type(labels)

            issues.append(
                GitHubIssue(
                    github_id=item["number"],
                    title=item.get("title", ""),
                    body=item.get("body", "") or "",
                    state=item.get("state", "open"),
                    labels=labels,
                    issue_type=issue_type,
                    html_url=item.get("html_url", ""),
                    created_at=item.get("created_at", ""),
                )
            )

        logger.info("Fetched %d issues for %s/%s", len(issues), owner, repo)
        return issues

    @staticmethod
    def _classify_type(labels: list[GitHubLabel]) -> IssueType:
        label_names = " ".join(lbl.name.lower() for lbl in labels)
        if "bug" in label_names:
            return IssueType.BUG
        if "feature" in label_names:
            return IssueType.FEATURE
        if "enhancement" in label_names:
            return IssueType.ENHANCEMENT
        return IssueType.OTHER
