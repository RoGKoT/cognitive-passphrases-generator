#!/usr/bin/env python3
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_FILE = REPO_ROOT / "pyproject.toml"


def load_git_tag() -> str | None:
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--exact-match"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None


def update_pyproject_version(tag: str) -> bool:
    if tag.startswith("v"):
        tag = tag[1:]

    content = PROJECT_FILE.read_text(encoding="utf-8")
    new_content = re.sub(
        r'(?m)^(version\s*=\s*)(["\'])([^"\']+)(["\'])',
        rf"\1\2{tag}\4",
        content,
        count=1,
    )
    if new_content != content:
        PROJECT_FILE.write_text(new_content, encoding="utf-8")
        print(f"Updated pyproject.toml version to {tag}")
        return True
    return False


def main() -> int:
    tag = load_git_tag()
    if not tag:
        return 0
    update_pyproject_version(tag)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
