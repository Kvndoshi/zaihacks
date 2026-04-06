"""Codebase analyzer — derives tech-stack, architecture patterns, and a
human-readable summary from a list of FileInfo objects using LLM analysis."""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from typing import Any, Optional

from backend.models.codebase import (
    ArchitecturePattern,
    CodebaseAnalysis,
    FileInfo,
    TechStackInfo,
)

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM_PROMPT = """\
You are a senior software architect analyzing a codebase.

Given the file listing and sample file contents, respond with a JSON object:
{
  "summary": "A 3-5 sentence overview of the project's purpose and structure.",
  "architecture_patterns": [
    {
      "name": "Pattern Name (e.g., MVC, Microservices, Monolith, Event-Driven)",
      "description": "Brief explanation of how this pattern is used.",
      "confidence": 0.85
    }
  ]
}

Be specific and grounded in the actual files you see. If unsure, assign
lower confidence scores. Identify 1-5 patterns.
"""

# Well-known framework indicators in package.json dependencies
_JS_FRAMEWORK_INDICATORS: dict[str, str] = {
    "react": "React",
    "react-dom": "React",
    "next": "Next.js",
    "vue": "Vue.js",
    "nuxt": "Nuxt.js",
    "svelte": "Svelte",
    "@sveltejs/kit": "SvelteKit",
    "angular": "Angular",
    "@angular/core": "Angular",
    "express": "Express.js",
    "fastify": "Fastify",
    "koa": "Koa",
    "hono": "Hono",
    "nest": "NestJS",
    "@nestjs/core": "NestJS",
    "gatsby": "Gatsby",
    "remix": "Remix",
    "astro": "Astro",
    "tailwindcss": "Tailwind CSS",
    "prisma": "Prisma",
    "drizzle-orm": "Drizzle ORM",
    "mongoose": "Mongoose",
    "sequelize": "Sequelize",
    "typeorm": "TypeORM",
    "socket.io": "Socket.IO",
    "three": "Three.js",
    "electron": "Electron",
    "vite": "Vite",
    "webpack": "Webpack",
    "esbuild": "esbuild",
}

# Well-known Python framework indicators in requirements.txt / pyproject.toml
_PY_FRAMEWORK_INDICATORS: dict[str, str] = {
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "starlette": "Starlette",
    "tornado": "Tornado",
    "aiohttp": "aiohttp",
    "celery": "Celery",
    "sqlalchemy": "SQLAlchemy",
    "alembic": "Alembic",
    "pydantic": "Pydantic",
    "langchain": "LangChain",
    "langgraph": "LangGraph",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "scikit-learn": "scikit-learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "pytest": "pytest",
    "uvicorn": "Uvicorn",
    "gunicorn": "Gunicorn",
    "redis": "Redis (Python)",
    "motor": "Motor (async MongoDB)",
    "pymongo": "PyMongo",
    "psycopg2": "PostgreSQL (psycopg2)",
    "asyncpg": "PostgreSQL (asyncpg)",
}

# Database indicators across languages
_DB_INDICATORS: dict[str, str] = {
    "mongodb": "MongoDB",
    "mongoose": "MongoDB",
    "motor": "MongoDB",
    "pymongo": "MongoDB",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "psycopg2": "PostgreSQL",
    "asyncpg": "PostgreSQL",
    "pg": "PostgreSQL",
    "mysql": "MySQL",
    "mysql2": "MySQL",
    "sqlite": "SQLite",
    "aiosqlite": "SQLite",
    "redis": "Redis",
    "ioredis": "Redis",
    "dynamodb": "DynamoDB",
    "firestore": "Firestore",
    "firebase": "Firebase",
    "supabase": "Supabase (PostgreSQL)",
    "prisma": "Prisma ORM",
    "drizzle": "Drizzle ORM",
    "sequelize": "Sequelize ORM",
    "typeorm": "TypeORM",
    "sqlalchemy": "SQLAlchemy",
    "neo4j": "Neo4j",
    "elasticsearch": "Elasticsearch",
    "cassandra": "Cassandra",
}

# Key filenames that signal entry points or important structure
_KEY_FILE_PATTERNS: set[str] = {
    "main",
    "app",
    "index",
    "server",
    "config",
    "settings",
    "models",
    "schema",
    "routes",
    "router",
    "views",
    "controllers",
    "handlers",
    "middleware",
    "database",
    "db",
    "auth",
    "api",
    "urls",
    "manage",
}


class CodebaseAnalyzer:
    """Analyzes codebase structure, tech stack, and architecture using
    static analysis complemented by LLM-powered pattern recognition."""

    def __init__(self, llm_client):
        self.llm = llm_client

    async def analyze(
        self,
        files: list[FileInfo],
        repo_url: Optional[str] = None,
        session_id: Optional[str] = None,
        root_dir: Optional[str] = None,
    ) -> CodebaseAnalysis:
        """Analyze codebase structure and tech stack.

        Args:
            files: List of FileInfo objects from the importer.
            repo_url: Optional source repository URL.
            session_id: Optional session to associate the analysis with.
            root_dir: Optional root directory path for reading file contents.

        Returns:
            A complete CodebaseAnalysis model.
        """
        # 1. Parse tech stack from package/config files
        tech_stack = self._parse_tech_stack(files, root_dir)

        # 2. Count files by language
        lang_counts: dict[str, int] = Counter()
        for f in files:
            if f.language and f.language != "Other":
                lang_counts[f.language] += 1
        tech_stack.languages = dict(lang_counts.most_common())

        # 3. Identify key files
        key_files = self._identify_key_files(files)

        # 4. Sample content from key files for LLM analysis
        samples = self._sample_file_contents(key_files, root_dir)

        # 5. LLM architecture analysis
        architecture_patterns: list[ArchitecturePattern] = []
        summary = ""
        try:
            llm_result = await self._llm_analyze(files, samples, tech_stack)
            summary = llm_result.get("summary", "")
            for pat in llm_result.get("architecture_patterns", []):
                architecture_patterns.append(
                    ArchitecturePattern(
                        name=pat.get("name", "Unknown"),
                        description=pat.get("description", ""),
                        confidence=min(1.0, max(0.0, float(pat.get("confidence", 0.5)))),
                    )
                )
        except Exception:
            logger.exception("LLM analysis failed; continuing with static analysis only")
            summary = self._generate_fallback_summary(files, tech_stack)

        total_size = sum(f.size for f in files)

        return CodebaseAnalysis(
            session_id=session_id,
            repo_url=repo_url,
            tech_stack=tech_stack,
            architecture_patterns=architecture_patterns,
            key_files=key_files,
            summary=summary,
            file_count=len(files),
            total_size=total_size,
        )

    # ------------------------------------------------------------------
    # Tech-stack parsing
    # ------------------------------------------------------------------

    def _parse_tech_stack(
        self, files: list[FileInfo], root_dir: Optional[str]
    ) -> TechStackInfo:
        """Extract tech stack information from package/config files."""
        frameworks: set[str] = set()
        package_managers: set[str] = set()
        databases: set[str] = set()

        file_paths = {f.path for f in files}
        file_names = {os.path.basename(f.path) for f in files}

        # Detect package managers
        if "package.json" in file_names:
            package_managers.add("npm")
        if "yarn.lock" in file_names:
            package_managers.add("yarn")
        if "pnpm-lock.yaml" in file_names:
            package_managers.add("pnpm")
        if "bun.lockb" in file_names:
            package_managers.add("bun")
        if "requirements.txt" in file_names or "pyproject.toml" in file_names:
            package_managers.add("pip")
        if "Pipfile" in file_names:
            package_managers.add("pipenv")
        if "poetry.lock" in file_names:
            package_managers.add("poetry")
        if "Cargo.toml" in file_names:
            package_managers.add("cargo")
        if "go.mod" in file_names:
            package_managers.add("go modules")
        if "Gemfile" in file_names:
            package_managers.add("bundler")
        if "composer.json" in file_names:
            package_managers.add("composer")

        # Parse actual dependency files if root_dir is available
        if root_dir:
            self._parse_package_json(root_dir, files, frameworks, databases)
            self._parse_requirements_txt(root_dir, files, frameworks, databases)
            self._parse_pyproject_toml(root_dir, files, frameworks, databases)
            self._parse_go_mod(root_dir, files, frameworks)
            self._parse_cargo_toml(root_dir, files, frameworks)

        # Detect from file presence even without reading contents
        if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
            frameworks.add("Docker")
        if any("kubernetes" in f.path.lower() or "k8s" in f.path.lower() for f in files):
            frameworks.add("Kubernetes")

        return TechStackInfo(
            frameworks=sorted(frameworks),
            package_managers=sorted(package_managers),
            databases=sorted(databases),
        )

    @staticmethod
    def _parse_package_json(
        root_dir: str,
        files: list[FileInfo],
        frameworks: set[str],
        databases: set[str],
    ) -> None:
        """Parse package.json files for dependency information."""
        pkg_files = [f for f in files if os.path.basename(f.path) == "package.json"]
        for pf in pkg_files[:3]:  # check up to 3 package.json files
            full_path = os.path.join(root_dir, pf.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    data = json.load(fh)
                all_deps: dict[str, str] = {}
                all_deps.update(data.get("dependencies", {}))
                all_deps.update(data.get("devDependencies", {}))

                for dep_name in all_deps:
                    dep_lower = dep_name.lower()
                    if dep_lower in _JS_FRAMEWORK_INDICATORS:
                        frameworks.add(_JS_FRAMEWORK_INDICATORS[dep_lower])
                    if dep_lower in _DB_INDICATORS:
                        databases.add(_DB_INDICATORS[dep_lower])
            except (OSError, json.JSONDecodeError):
                continue

    @staticmethod
    def _parse_requirements_txt(
        root_dir: str,
        files: list[FileInfo],
        frameworks: set[str],
        databases: set[str],
    ) -> None:
        """Parse requirements.txt for Python dependencies."""
        req_files = [f for f in files if os.path.basename(f.path) == "requirements.txt"]
        for rf in req_files[:3]:
            full_path = os.path.join(root_dir, rf.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line or line.startswith("#") or line.startswith("-"):
                            continue
                        # Extract package name (before any version specifier)
                        pkg = line.split("==")[0].split(">=")[0].split("<=")[0]
                        pkg = pkg.split("[")[0].strip().lower()
                        if pkg in _PY_FRAMEWORK_INDICATORS:
                            frameworks.add(_PY_FRAMEWORK_INDICATORS[pkg])
                        if pkg in _DB_INDICATORS:
                            databases.add(_DB_INDICATORS[pkg])
            except OSError:
                continue

    @staticmethod
    def _parse_pyproject_toml(
        root_dir: str,
        files: list[FileInfo],
        frameworks: set[str],
        databases: set[str],
    ) -> None:
        """Parse pyproject.toml for Python dependencies (best-effort)."""
        toml_files = [f for f in files if os.path.basename(f.path) == "pyproject.toml"]
        for tf in toml_files[:2]:
            full_path = os.path.join(root_dir, tf.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read()
                # Simple line-based scan — avoids requiring a TOML parser
                for line in content.splitlines():
                    line_lower = line.lower().strip()
                    for pkg, name in _PY_FRAMEWORK_INDICATORS.items():
                        if pkg in line_lower:
                            frameworks.add(name)
                    for pkg, name in _DB_INDICATORS.items():
                        if pkg in line_lower:
                            databases.add(name)
            except OSError:
                continue

    @staticmethod
    def _parse_go_mod(
        root_dir: str,
        files: list[FileInfo],
        frameworks: set[str],
    ) -> None:
        """Detect Go frameworks from go.mod."""
        go_mod_files = [f for f in files if os.path.basename(f.path) == "go.mod"]
        for gf in go_mod_files[:1]:
            full_path = os.path.join(root_dir, gf.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read().lower()
                if "gin-gonic" in content:
                    frameworks.add("Gin")
                if "gorilla/mux" in content:
                    frameworks.add("Gorilla Mux")
                if "labstack/echo" in content:
                    frameworks.add("Echo")
                if "fiber" in content:
                    frameworks.add("Fiber")
            except OSError:
                pass

    @staticmethod
    def _parse_cargo_toml(
        root_dir: str,
        files: list[FileInfo],
        frameworks: set[str],
    ) -> None:
        """Detect Rust frameworks from Cargo.toml."""
        cargo_files = [f for f in files if os.path.basename(f.path) == "Cargo.toml"]
        for cf in cargo_files[:1]:
            full_path = os.path.join(root_dir, cf.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    content = fh.read().lower()
                if "actix" in content:
                    frameworks.add("Actix Web")
                if "axum" in content:
                    frameworks.add("Axum")
                if "rocket" in content:
                    frameworks.add("Rocket")
                if "tokio" in content:
                    frameworks.add("Tokio")
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Key file identification
    # ------------------------------------------------------------------

    def _identify_key_files(self, files: list[FileInfo]) -> list[FileInfo]:
        """Find entry points, configs, models, and other structurally
        important files."""
        key: list[FileInfo] = []
        seen_paths: set[str] = set()

        for f in files:
            basename = os.path.basename(f.path)
            stem = os.path.splitext(basename)[0].lower()

            is_key = (
                stem in _KEY_FILE_PATTERNS
                or f.is_config
                # top-level source files
                or (f.path.count("/") <= 1 and f.language not in ("Other", "Markdown", "Text"))
            )

            if is_key and f.path not in seen_paths:
                key.append(f)
                seen_paths.add(f.path)

        # Sort: configs first, then by path depth (shallower = more important)
        key.sort(key=lambda x: (not x.is_config, x.path.count("/"), x.path))
        return key[:50]  # cap to avoid oversized prompts

    # ------------------------------------------------------------------
    # File content sampling
    # ------------------------------------------------------------------

    @staticmethod
    def _sample_file_contents(
        key_files: list[FileInfo],
        root_dir: Optional[str],
        max_files: int = 10,
        max_lines: int = 100,
    ) -> list[dict[str, str]]:
        """Read the first *max_lines* of the top *max_files* key files.

        Returns a list of ``{"path": ..., "content": ...}`` dicts.
        """
        if not root_dir:
            return []

        samples: list[dict[str, str]] = []
        for f in key_files[:max_files]:
            full_path = os.path.join(root_dir, f.path)
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as fh:
                    lines = []
                    for i, line in enumerate(fh):
                        if i >= max_lines:
                            break
                        lines.append(line)
                    content = "".join(lines)
                    if content.strip():
                        samples.append({"path": f.path, "content": content})
            except OSError:
                continue

        return samples

    # ------------------------------------------------------------------
    # LLM analysis
    # ------------------------------------------------------------------

    async def _llm_analyze(
        self,
        files: list[FileInfo],
        samples: list[dict[str, str]],
        tech_stack: TechStackInfo,
    ) -> dict[str, Any]:
        """Send file listing + samples to the LLM for architecture analysis."""
        # Build a concise file tree
        file_list = "\n".join(f"- {f.path} ({f.language}, {f.size}B)" for f in files[:200])

        # Build sample snippets
        sample_text = ""
        if samples:
            parts = []
            for s in samples:
                parts.append(f"### {s['path']}\n```\n{s['content']}\n```")
            sample_text = "\n\n".join(parts)

        prompt_parts = [
            f"## File Listing ({len(files)} files total)\n{file_list}",
        ]

        if tech_stack.frameworks:
            prompt_parts.append(f"## Detected Frameworks\n{', '.join(tech_stack.frameworks)}")
        if tech_stack.databases:
            prompt_parts.append(f"## Detected Databases\n{', '.join(tech_stack.databases)}")

        if sample_text:
            prompt_parts.append(f"## Sample File Contents\n{sample_text}")

        prompt_parts.append(
            "Analyze the project structure and identify architecture patterns. "
            "Respond with the JSON format specified in the system prompt."
        )

        prompt = "\n\n".join(prompt_parts)

        result = await self.llm.structured_output(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.3,
        )
        return result

    # ------------------------------------------------------------------
    # Fallback summary
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_fallback_summary(
        files: list[FileInfo], tech_stack: TechStackInfo
    ) -> str:
        """Generate a basic summary without LLM when analysis fails."""
        lang_summary = ", ".join(
            f"{lang} ({count})"
            for lang, count in sorted(
                tech_stack.languages.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:5]
        )

        parts = [f"Codebase with {len(files)} files."]
        if lang_summary:
            parts.append(f"Languages: {lang_summary}.")
        if tech_stack.frameworks:
            parts.append(f"Frameworks: {', '.join(tech_stack.frameworks)}.")
        if tech_stack.databases:
            parts.append(f"Databases: {', '.join(tech_stack.databases)}.")

        return " ".join(parts)
