"""Codebase importer — clones repos or walks local directories and returns
structured FileInfo lists for downstream analysis."""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

import git  # gitpython

from backend.models.codebase import FileInfo

logger = logging.getLogger(__name__)

# Directories to always skip
_IGNORE_DIRS: set[str] = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    ".next",
    ".cache",
    "target",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".eggs",
    "egg-info",
    ".idea",
    ".vscode",
    ".DS_Store",
    "coverage",
    ".turbo",
}

# File extensions to skip
_IGNORE_EXTENSIONS: set[str] = {
    ".pyc",
    ".pyo",
    ".so",
    ".dll",
    ".exe",
    ".bin",
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".mp3",
    ".mp4",
    ".avi",
    ".mov",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    ".pdf",
    ".doc",
    ".docx",
}

# Extension -> language mapping
_EXTENSION_MAP: dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".pyx": "Python",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".mts": "TypeScript",
    ".cts": "TypeScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".c": "C",
    ".h": "C/C++ Header",
    ".hpp": "C++ Header",
    ".swift": "Swift",
    ".dart": "Dart",
    ".lua": "Lua",
    ".r": "R",
    ".R": "R",
    ".jl": "Julia",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".zig": "Zig",
    ".v": "V",
    ".nim": "Nim",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".less": "Less",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".sql": "SQL",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".proto": "Protobuf",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".json": "JSON",
    ".xml": "XML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".txt": "Text",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".fish": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".tf": "Terraform",
    ".hcl": "HCL",
    ".sol": "Solidity",
}

# Filenames that are considered config files
_CONFIG_FILENAMES: set[str] = {
    "package.json",
    "package-lock.json",
    "tsconfig.json",
    "tsconfig.base.json",
    "jsconfig.json",
    "requirements.txt",
    "setup.py",
    "setup.cfg",
    "pyproject.toml",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "Gemfile",
    "Gemfile.lock",
    "composer.json",
    "composer.lock",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Makefile",
    "CMakeLists.txt",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    ".gitignore",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.js",
    ".prettierrc.json",
    "babel.config.js",
    "webpack.config.js",
    "vite.config.ts",
    "vite.config.js",
    "next.config.js",
    "next.config.mjs",
    "tailwind.config.js",
    "tailwind.config.ts",
    "postcss.config.js",
    ".env.example",
    ".env.template",
    "nginx.conf",
    "Procfile",
    "vercel.json",
    "netlify.toml",
    "fly.toml",
    "render.yaml",
}

# Patterns that make a filename a config file
_CONFIG_PATTERNS: list[str] = [
    "config.",
    ".config.",
    "rc.",
    ".rc",
    "settings.",
    ".env",
]


class CodebaseImporter:
    """Imports a codebase from a git repo URL or a local directory and
    returns a structured list of FileInfo objects."""

    IGNORE_DIRS = _IGNORE_DIRS
    IGNORE_EXTENSIONS = _IGNORE_EXTENSIONS

    async def import_from_git(
        self,
        repo_url: str,
        target_dir: Optional[str] = None,
    ) -> tuple[str, list[FileInfo]]:
        """Clone a git repository and walk its files.

        Args:
            repo_url: HTTPS or SSH URL of the git repository.
            target_dir: Optional directory to clone into.  If ``None``,
                        a temporary directory is created.

        Returns:
            A tuple of ``(clone_path, list_of_FileInfo)``.
        """
        clone_path = target_dir or tempfile.mkdtemp(prefix="friction_repo_")
        logger.info("Cloning %s into %s", repo_url, clone_path)

        # gitpython clone is synchronous; run in executor to avoid blocking
        import asyncio

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: git.Repo.clone_from(repo_url, clone_path, depth=1),
        )

        files = self.walk_directory(clone_path)
        logger.info(
            "Cloned %s — found %d files", repo_url, len(files)
        )
        return clone_path, files

    async def import_from_directory(self, directory: str) -> list[FileInfo]:
        """Walk an existing local directory.

        Args:
            directory: Absolute or relative path to the directory.

        Returns:
            List of FileInfo objects for all non-ignored files.
        """
        directory = os.path.abspath(directory)
        if not os.path.isdir(directory):
            raise FileNotFoundError(f"Directory not found: {directory}")

        files = self.walk_directory(directory)
        logger.info("Imported %d files from %s", len(files), directory)
        return files

    def walk_directory(self, root: str) -> list[FileInfo]:
        """Walk a directory tree, respecting ignore rules.

        Args:
            root: The root directory to walk.

        Returns:
            A list of FileInfo objects with paths relative to *root*.
        """
        root = os.path.abspath(root)
        files: list[FileInfo] = []

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune ignored directories in-place so os.walk skips them
            dirnames[:] = [
                d for d in dirnames
                if d not in _IGNORE_DIRS
                and not d.endswith(".egg-info")
            ]

            for fname in filenames:
                ext = os.path.splitext(fname)[1].lower()
                if ext in _IGNORE_EXTENSIONS:
                    continue

                full_path = os.path.join(dirpath, fname)
                try:
                    size = os.path.getsize(full_path)
                except OSError:
                    continue

                # Skip very large files (> 2 MB) — likely generated or binary
                if size > 2 * 1024 * 1024:
                    continue

                rel_path = os.path.relpath(full_path, root).replace("\\", "/")
                language = self._detect_language(ext)
                is_config = self._is_config_file(fname)

                files.append(
                    FileInfo(
                        path=rel_path,
                        size=size,
                        language=language,
                        is_config=is_config,
                    )
                )

        return files

    @staticmethod
    def _detect_language(ext: str) -> str:
        """Map a file extension to a human-readable language name."""
        return _EXTENSION_MAP.get(ext.lower(), "Other")

    @staticmethod
    def _is_config_file(filename: str) -> bool:
        """Determine whether a filename represents a configuration file."""
        if filename in _CONFIG_FILENAMES:
            return True

        lower = filename.lower()
        for pattern in _CONFIG_PATTERNS:
            if pattern in lower:
                return True

        # Dotfiles that are not source code
        if lower.startswith(".") and not any(
            lower.endswith(ext) for ext in (".py", ".js", ".ts", ".go", ".rs")
        ):
            return True

        return False
