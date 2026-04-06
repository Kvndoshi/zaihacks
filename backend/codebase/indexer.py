"""Codebase indexer — generates a structured text map of a codebase
from filesystem traversal and pattern matching. No LLM calls needed."""

from __future__ import annotations

import os
from collections import defaultdict
from typing import Optional

from backend.models.codebase import CodebaseAnalysis, FileInfo

# Directories to exclude from the tree
_EXCLUDED_DIRS: set[str] = {
    "node_modules",
    ".git",
    "__pycache__",
    "venv",
    ".venv",
    "env",
    ".env",
    "dist",
    "build",
    ".next",
    ".nuxt",
    ".cache",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "coverage",
    ".coverage",
    "htmlcov",
    ".idea",
    ".vscode",
    "vendor",
    "target",
    ".svn",
    ".hg",
    "bower_components",
    ".terraform",
}

# Common entry point filenames (stem, without extension)
_ENTRY_POINT_STEMS: set[str] = {
    "main",
    "app",
    "index",
    "server",
    "manage",
    "wsgi",
    "asgi",
    "cli",
    "run",
    "startup",
    "boot",
    "entrypoint",
}

# Config file names and patterns
_CONFIG_FILES: set[str] = {
    "package.json",
    "tsconfig.json",
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
    "go.sum",
    "Gemfile",
    "composer.json",
    "Makefile",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    ".gitignore",
    ".env.template",
    ".env.example",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.json",
    "jest.config.js",
    "jest.config.ts",
    "vite.config.ts",
    "vite.config.js",
    "webpack.config.js",
    "tailwind.config.js",
    "tailwind.config.ts",
    "postcss.config.js",
    "babel.config.js",
    "nginx.conf",
    "Procfile",
    ".github",
    "renovate.json",
    "vercel.json",
    "netlify.toml",
}

# Module/feature directory name patterns mapped to feature names
_MODULE_PATTERNS: dict[str, str] = {
    "auth": "Authentication",
    "login": "Authentication",
    "signup": "Authentication",
    "register": "Authentication",
    "api": "API",
    "routes": "API Routes",
    "routers": "API Routes",
    "controllers": "Controllers",
    "handlers": "Request Handlers",
    "views": "Views",
    "pages": "Pages",
    "components": "UI Components",
    "hooks": "React Hooks",
    "store": "State Management",
    "stores": "State Management",
    "redux": "State Management (Redux)",
    "context": "React Context",
    "models": "Data Models",
    "schemas": "Data Schemas",
    "entities": "Entities",
    "services": "Services",
    "utils": "Utilities",
    "helpers": "Helpers",
    "lib": "Library/Shared Code",
    "common": "Common/Shared Code",
    "shared": "Shared Code",
    "middleware": "Middleware",
    "middlewares": "Middleware",
    "database": "Database",
    "db": "Database",
    "migrations": "Database Migrations",
    "seeds": "Database Seeds",
    "config": "Configuration",
    "settings": "Configuration",
    "tests": "Tests",
    "test": "Tests",
    "__tests__": "Tests",
    "spec": "Tests",
    "e2e": "End-to-End Tests",
    "fixtures": "Test Fixtures",
    "static": "Static Assets",
    "public": "Public Assets",
    "assets": "Assets",
    "images": "Images",
    "styles": "Styles",
    "css": "Styles",
    "templates": "Templates",
    "emails": "Email Templates",
    "notifications": "Notifications",
    "websocket": "WebSocket",
    "ws": "WebSocket",
    "events": "Events",
    "jobs": "Background Jobs",
    "workers": "Workers",
    "tasks": "Background Tasks",
    "queues": "Job Queues",
    "cron": "Scheduled Tasks",
    "plugins": "Plugins",
    "extensions": "Extensions",
    "types": "Type Definitions",
    "interfaces": "Interfaces",
    "decorators": "Decorators",
    "guards": "Guards",
    "pipes": "Pipes",
    "filters": "Filters",
    "interceptors": "Interceptors",
    "docs": "Documentation",
    "scripts": "Scripts",
    "tools": "Tools",
    "deploy": "Deployment",
    "infra": "Infrastructure",
    "terraform": "Infrastructure (Terraform)",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "ci": "CI/CD",
    "analytics": "Analytics",
    "logging": "Logging",
    "monitoring": "Monitoring",
    "cache": "Caching",
    "i18n": "Internationalization",
    "locales": "Localization",
    "graphql": "GraphQL",
    "grpc": "gRPC",
    "proto": "Protocol Buffers",
}


class CodebaseIndexer:
    """Generates a structured text index/map of a codebase from the filesystem."""

    def generate_index(
        self, repo_path: str, analysis: CodebaseAnalysis
    ) -> str:
        """Generate a structured codebase index/map as text.

        Args:
            repo_path: Path to the cloned repository on disk.
            analysis: The CodebaseAnalysis with tech stack and key files info.

        Returns:
            A plain-text codebase map.
        """
        sections: list[str] = []

        # Header
        repo_name = analysis.repo_url or os.path.basename(repo_path)
        sections.append(f"# Codebase Map: {repo_name}")
        sections.append(f"# {analysis.file_count} files, {_format_size(analysis.total_size)}")
        sections.append("")

        # 1. Directory tree
        tree = self._generate_tree(repo_path, max_depth=4)
        sections.append("## Directory Structure")
        sections.append(tree)
        sections.append("")

        # 2. Entry points
        entry_points = self._find_entry_points(repo_path)
        if entry_points:
            sections.append("## Entry Points")
            for ep in entry_points:
                sections.append(f"  - {ep}")
            sections.append("")

        # 3. Config files
        config_files = self._find_config_files(repo_path)
        if config_files:
            sections.append("## Configuration Files")
            for cf in config_files:
                sections.append(f"  - {cf}")
            sections.append("")

        # 4. Module/feature map
        module_map = self._build_module_map(repo_path)
        if module_map:
            sections.append("## Module / Feature Map")
            for feature, paths in sorted(module_map.items()):
                paths_display = ", ".join(sorted(paths)[:5])
                if len(paths) > 5:
                    paths_display += f" (+{len(paths) - 5} more)"
                sections.append(f"  {feature}:")
                sections.append(f"    {paths_display}")
            sections.append("")

        # 5. Key file summaries
        key_files = analysis.key_files[:15]
        if key_files:
            sections.append("## Key Files")
            for f in key_files:
                desc = _describe_file(f)
                sections.append(f"  - {f.path} -- {desc}")
            sections.append("")

        return "\n".join(sections)

    def _generate_tree(
        self, root: str, max_depth: int = 4
    ) -> str:
        """Generate an indented directory tree, like the `tree` command."""
        lines: list[str] = []
        root_name = os.path.basename(root) or root
        lines.append(root_name + "/")
        self._walk_tree(root, "", lines, current_depth=0, max_depth=max_depth)
        return "\n".join(lines)

    def _walk_tree(
        self,
        path: str,
        prefix: str,
        lines: list[str],
        current_depth: int,
        max_depth: int,
    ) -> None:
        """Recursive tree walker."""
        if current_depth >= max_depth:
            return

        try:
            entries = sorted(os.listdir(path))
        except OSError:
            return

        # Separate dirs and files, filter excluded dirs
        dirs: list[str] = []
        files: list[str] = []
        for entry in entries:
            full = os.path.join(path, entry)
            if os.path.isdir(full):
                if entry.lower() not in _EXCLUDED_DIRS and not entry.startswith("."):
                    dirs.append(entry)
            else:
                files.append(entry)

        all_entries = dirs + files
        for i, entry in enumerate(all_entries):
            is_last = i == len(all_entries) - 1
            connector = "`-- " if is_last else "|-- "
            full = os.path.join(path, entry)

            if os.path.isdir(full):
                lines.append(f"{prefix}{connector}{entry}/")
                extension = "    " if is_last else "|   "
                self._walk_tree(
                    full,
                    prefix + extension,
                    lines,
                    current_depth + 1,
                    max_depth,
                )
            else:
                lines.append(f"{prefix}{connector}{entry}")

    def _find_entry_points(self, root: str) -> list[str]:
        """Find likely entry point files."""
        entry_points: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip excluded directories
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in _EXCLUDED_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                stem = os.path.splitext(fname)[0].lower()
                if stem in _ENTRY_POINT_STEMS:
                    rel = os.path.relpath(os.path.join(dirpath, fname), root)
                    rel = rel.replace("\\", "/")
                    entry_points.append(rel)

        # Sort: shallower paths first
        entry_points.sort(key=lambda p: (p.count("/"), p))
        return entry_points[:20]

    def _find_config_files(self, root: str) -> list[str]:
        """Find configuration files."""
        config_files: list[str] = []
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in _EXCLUDED_DIRS and not d.startswith(".")
            ]
            for fname in filenames:
                if fname in _CONFIG_FILES or fname.lower() in _CONFIG_FILES:
                    rel = os.path.relpath(os.path.join(dirpath, fname), root)
                    rel = rel.replace("\\", "/")
                    config_files.append(rel)

        config_files.sort(key=lambda p: (p.count("/"), p))
        return config_files[:30]

    def _build_module_map(self, root: str) -> dict[str, list[str]]:
        """Group directories into feature/module categories based on name patterns."""
        module_map: dict[str, list[str]] = defaultdict(list)

        for dirpath, dirnames, _filenames in os.walk(root):
            dirnames[:] = [
                d for d in dirnames
                if d.lower() not in _EXCLUDED_DIRS and not d.startswith(".")
            ]
            for dname in dirnames:
                dname_lower = dname.lower()
                if dname_lower in _MODULE_PATTERNS:
                    feature = _MODULE_PATTERNS[dname_lower]
                    rel = os.path.relpath(os.path.join(dirpath, dname), root)
                    rel = rel.replace("\\", "/")
                    module_map[feature].append(f"{rel}/*")

        return dict(module_map)


def _format_size(size_bytes: int) -> str:
    """Format byte size to human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def _describe_file(f: FileInfo) -> str:
    """Generate a one-line description of a file based on its name and attributes."""
    basename = os.path.basename(f.path)
    stem = os.path.splitext(basename)[0].lower()
    ext = os.path.splitext(basename)[1].lower()

    if f.is_config:
        return f"Configuration file ({f.language})"

    descriptions: dict[str, str] = {
        "main": "Application entry point",
        "app": "Application setup/initialization",
        "index": "Module entry point / barrel export",
        "server": "Server setup and configuration",
        "config": "Configuration module",
        "settings": "Application settings",
        "models": "Data model definitions",
        "schema": "Schema definitions",
        "schemas": "Schema definitions",
        "routes": "Route definitions",
        "router": "Router configuration",
        "routers": "Router definitions",
        "views": "View handlers",
        "controllers": "Controller logic",
        "handlers": "Request handlers",
        "middleware": "Middleware definitions",
        "database": "Database setup/connection",
        "db": "Database configuration",
        "auth": "Authentication logic",
        "api": "API client/definitions",
        "urls": "URL routing configuration",
        "manage": "Management/CLI commands",
        "utils": "Utility functions",
        "helpers": "Helper functions",
        "constants": "Constants and enums",
        "types": "Type definitions",
        "store": "State management store",
        "test": "Test file",
        "spec": "Test specification",
    }

    if stem in descriptions:
        return f"{descriptions[stem]} ({f.language})"

    # Fallback: describe by language and directory
    parent = os.path.dirname(f.path)
    if parent:
        return f"{f.language} file in {parent}"
    return f"{f.language} source file"
