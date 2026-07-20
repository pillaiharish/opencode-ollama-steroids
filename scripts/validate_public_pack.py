#!/usr/bin/env python3
"""Validate the public starter kit before publishing."""
from __future__ import annotations

import argparse
import re
from pathlib import Path

REQUIRED_FILES = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".gitignore",
    ".github/workflows/sanity.yml",
    "AGENTS.md",
    "opencode.json",
    "project.local.env.example",
    ".opencode/agents/minimax-builder.md",
    ".opencode/agents/glm-reviewer.md",
    ".opencode/agents/model-inference-smoke.md",
    ".opencode/agents/model-tool-smoke.md",
    ".opencode/model-smoke/FIXTURE.txt",
    "templates/PROMPT_CODER_TEMPLATE.md",
    "templates/PROMPT_REVIEWER_TEMPLATE.md",
    "templates/SESSION_README_TEMPLATE.md",
    "scripts/new_prompt.zsh",
    "scripts/run_builder.zsh",
    "scripts/run_reviewer.zsh",
    "scripts/run_prompt_agents.zsh",
    "scripts/start_headless_server.zsh",
    "scripts/model_resolver.py",
    "scripts/model_runtime.zsh",
    "scripts/redact_sessions.py",
    "scripts/validate_public_pack.py",
    "scripts/doctor.zsh",
    "docs/quickstart.md",
    "docs/architecture.md",
    "docs/mcp-playbook.md",
    "docs/permission-model.md",
    "docs/session-storage-policy.md",
    "docs/redaction-checklist.md",
    "docs/screenshots-policy.md",
    "docs/model-matrix.md",
    "docs/release-checklist.md",
    "examples/tiny-python-app/README.md",
    "tests/test_model_resolver.py",
    "tests/test_launcher_integration.py",
    "tests/test_model_resolver_live.py",
]

REQUIRED_SKILLS = [
    "opencode-ollama-agent-guardrails",
    "safe-session-redaction",
    "test-first-agent-loop",
]

STRICT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-macos-path", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    ("private-linux-home-path", re.compile(r"/home/[A-Za-z0-9._-]+")),
    ("private-windows-user-path", re.compile(r"C:\\Users\\[A-Za-z0-9._-]+", re.IGNORECASE)),
    ("email-address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{16,}\b")),
    ("openai-or-similar-secret", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")),
    ("private-key-marker", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "generic-secret-assignment",
        re.compile(r"(?i)\b(api[_-]?key|token|secret|password|auth[_-]?token|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]+"),
    ),
]

TEXT_SUFFIXES = {".md", ".txt", ".json", ".jsonc", ".py", ".zsh", ".sh", ".yaml", ".yml", ".toml", ".gitignore", ""}
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", "coverage"}
SCREENSHOT_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
RAW_SESSION_SUFFIXES = {".raw.log", ".events.jsonl"}

LOCAL_PATH_ALLOWLIST_SNIPPETS = [
    "`/Users",
    "`/home",
    "`C:\\Users",
    "r\"/Users/",
    "r\"/home/",
    "re.compile(r\"/Users/",
    "re.compile(r\"/home/",
    "C:\\Users\\[",
]

SECRET_EXAMPLE_ALLOWLIST = [
    "<REDACTED",
    "replace_me",
    "your_",
    "YOUR_",
    "example",
    "token names",
    "token,",
    "tokens,",
    "passwords,",
    "password is",
    "password before",
    "password>",
    "api keys",
    "API keys",
]


def iter_files(paths: list[Path]):
    for root in paths:
        if root.is_file():
            yield root
            continue
        for path in root.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.is_file() and (path.suffix.lower() in TEXT_SUFFIXES or path.name == ".gitignore"):
                yield path


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def allowed_pattern_hit(name: str, snippet: str) -> bool:
    if name in {"private-macos-path", "private-linux-home-path", "private-windows-user-path"}:
        return any(marker in snippet for marker in LOCAL_PATH_ALLOWLIST_SNIPPETS)
    if name == "generic-secret-assignment":
        return any(marker in snippet for marker in SECRET_EXAMPLE_ALLOWLIST)
    return "<REDACTED" in snippet


def validate_required(root: Path, failures: list[str]) -> None:
    for rel in REQUIRED_FILES:
        if not (root / rel).is_file():
            failures.append(f"missing required file: {rel}")

    for skill in REQUIRED_SKILLS:
        path = root / ".opencode" / "skills" / skill / "SKILL.md"
        if not path.is_file():
            failures.append(f"missing required skill: {skill}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        expected_name = f"name: {skill}"
        if not text.startswith("---\n") or expected_name not in text or "description:" not in text:
            failures.append(f"invalid skill frontmatter: {path}")

    if (root / "skills").exists():
        failures.append("old top-level skills directory should not be present")


def validate_blocked_files(root: Path, failures: list[str]) -> None:
    for path in root.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.name == ".DS_Store":
            failures.append(f"local metadata file present: {path}")
        if path.name == ".env" or path.name.startswith(".env."):
            if path.name != ".env.example":
                failures.append(f"env file present: {path}")
        if any(path.name.endswith(suffix) for suffix in RAW_SESSION_SUFFIXES):
            failures.append(f"raw session file present: {path}")
        if path.name.startswith("opencode-session-") and path.suffix == ".json":
            failures.append(f"raw OpenCode session export present: {path}")
        if path.suffix.lower() in SCREENSHOT_SUFFIXES:
            failures.append(f"screenshot file present: {path}")

    for allowed in [root / "agent-sessions", root / "screenshots"]:
        if allowed.exists():
            for path in allowed.rglob("*"):
                if path.is_file() and path.name != ".gitkeep":
                    failures.append(f"only .gitkeep is allowed under {allowed}: {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*", type=Path, default=[Path(".")])
    args = parser.parse_args()

    failures: list[str] = []
    root = Path(".")
    validate_required(root, failures)
    validate_blocked_files(root, failures)

    for path in iter_files(args.paths):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover
            failures.append(f"{path}: could not read: {exc}")
            continue
        for name, pattern in STRICT_PATTERNS:
            for match in pattern.finditer(text):
                snippet = text[max(0, match.start() - 80) : match.end() + 80]
                if allowed_pattern_hit(name, snippet):
                    continue
                failures.append(f"{path}:{line_for_offset(text, match.start())}: {name}: {match.group(0)[:100]}")

    if failures:
        print("Public-pack validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Public-pack validation passed. Manual review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
