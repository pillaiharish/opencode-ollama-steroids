#!/usr/bin/env python3
"""Scan and optionally redact local agent session material.

This is a convenience filter, not a substitute for manual review. It exits
non-zero when suspicious material is found, even when redacted copies are
written.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    ("macos-local-path", re.compile(r"/Users/[^\s:'\")<>]+"), "<REDACTED_LOCAL_PATH>"),
    ("linux-home-path", re.compile(r"/home/[^\s:'\")<>]+"), "<REDACTED_LOCAL_PATH>"),
    ("windows-user-path", re.compile(r"C:\\Users\\[^\s:'\")<>]+", re.IGNORECASE), "<REDACTED_LOCAL_PATH>"),
    ("email-address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "<REDACTED_EMAIL>"),
    (
        "secret-assignment",
        re.compile(r"(?i)\b(api[_-]?key|token|secret|password|auth[_-]?token|access[_-]?token)\s*[:=]\s*['\"]?[^\s'\"]+"),
        r"\1=<REDACTED_SECRET>",
    ),
    ("dotenv-assignment", re.compile(r"(?m)^[A-Z][A-Z0-9_]*(KEY|TOKEN|SECRET|PASSWORD)=.+$"), "<REDACTED_ENV_VALUE>"),
    ("private-key-marker", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "<REDACTED_PRIVATE_KEY>"),
    ("openai-style-secret", re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{16,}\b"), "<REDACTED_SECRET>"),
    ("github-token", re.compile(r"(?i)\bgh[pousr]_[A-Za-z0-9_]{16,}\b"), "<REDACTED_SECRET>"),
    ("raw-log-file", re.compile(r"\b[A-Za-z0-9._-]+\.raw\.log\b"), "<REDACTED_RAW_LOG_REFERENCE>"),
    ("events-jsonl-file", re.compile(r"\b[A-Za-z0-9._-]+\.events\.jsonl\b"), "<REDACTED_EVENT_LOG_REFERENCE>"),
    ("opencode-session-export", re.compile(r"\bopencode-session-[A-Za-z0-9._-]+\.json\b"), "<REDACTED_SESSION_EXPORT>"),
    ("screenshot-reference", re.compile(r"\b[^\s]+\.(png|jpg|jpeg|webp)\b", re.IGNORECASE), "<REDACTED_SCREENSHOT_REFERENCE>"),
]

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".log",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".toml",
    ".env",
    ".zsh",
    ".sh",
    ".py",
}
SKIP_DIRS = {".git", "node_modules", ".venv", "__pycache__", "dist", "build"}


def redact_text(text: str) -> str:
    for _, pattern, replacement in PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def should_process(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in TEXT_SUFFIXES


def iter_text_files(source: Path) -> list[Path]:
    if source.is_file():
        return [source] if should_process(source) else []
    paths: list[Path] = []
    for path in source.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if should_process(path):
            paths.append(path)
    return paths


def line_for_offset(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="Write redacted copies under this directory.")
    args = parser.parse_args()

    source = args.path
    if not source.exists():
        raise SystemExit(f"Path not found: {source}")

    paths = iter_text_files(source)
    findings: list[str] = []

    for path in paths:
        text = path.read_text(encoding="utf-8", errors="replace")
        for name, pattern, _ in PATTERNS:
            for match in pattern.finditer(text):
                findings.append(f"{path}:{line_for_offset(text, match.start())}: {name}: {match.group(0)[:100]}")

        if not args.out:
            continue

        redacted = redact_text(text)
        rel = path.relative_to(source) if source.is_dir() else Path(path.name)
        out_path = args.out / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(redacted, encoding="utf-8")
        print(out_path)

    if findings:
        print("Suspicious session material found:")
        for finding in findings:
            print(f"- {finding}")
        if args.out:
            print("Redacted copies were written, but manual review is still required.")
        return 1

    print("No obvious session leaks found. Manual review still required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
