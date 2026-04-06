"""Models for codebase analysis / repo ingestion."""

from __future__ import annotations

import re
import uuid
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# GitHub Issue models
# ---------------------------------------------------------------------------


class GitHubLabel(BaseModel):
    name: str
    color: str = ""


class IssueType(str, Enum):
    BUG = "bug"
    FEATURE = "feature"
    ENHANCEMENT = "enhancement"
    OTHER = "other"


class GitHubIssue(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    github_id: int
    title: str
    body: str = ""
    state: str = "open"
    labels: list[GitHubLabel] = Field(default_factory=list)
    issue_type: IssueType = IssueType.OTHER
    html_url: str = ""
    created_at: str = ""


def parse_github_owner_repo(url: str) -> tuple[str, str] | None:
    """Extract (owner, repo) from a GitHub URL. Returns None if not GitHub."""
    m = re.search(r"github\.com[:/]([^/]+)/([^/.]+)", url)
    if not m:
        return None
    return m.group(1), m.group(2)


class FileInfo(BaseModel):
    path: str
    size: int
    language: str
    is_config: bool = False


class TechStackInfo(BaseModel):
    languages: dict[str, int] = Field(
        default_factory=dict,
        description="Language name -> file count",
    )
    frameworks: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    databases: list[str] = Field(default_factory=list)


class ArchitecturePattern(BaseModel):
    name: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)


class CodebaseAnalysis(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    session_id: Optional[str] = None
    repo_url: Optional[str] = None
    tech_stack: TechStackInfo = Field(default_factory=TechStackInfo)
    architecture_patterns: list[ArchitecturePattern] = Field(default_factory=list)
    key_files: list[FileInfo] = Field(default_factory=list)
    summary: str = ""
    file_count: int = 0
    total_size: int = 0
    codebase_index: Optional[str] = None
