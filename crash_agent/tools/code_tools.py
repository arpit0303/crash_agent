import os
import subprocess
from pathlib import Path

REPO_DIR = Path(os.getenv("TARGET_REPO_DIR", Path(__file__).resolve().parent.parent / "repositories" / "Crash-Fix-AI")).resolve()
SOURCE_SUFFIXES = (".kt", ".java", ".kts", ".xml")
SKIP_DIRS = {"build", ".git", ".gradle", ".idea"}


def _safe(path: str) -> Path:
    p = (REPO_DIR / path).resolve()
    if REPO_DIR not in p.parents and p != REPO_DIR:
        raise ValueError("Path escapes the repository")
    if any(part in SKIP_DIRS for part in p.relative_to(REPO_DIR).parts):
        raise ValueError("Path is in a protected/build directory")
    return p


def find_source_file(file_name: str) -> list[str]:
    """Find source files in the target repository by file name (e.g. 'MainActivity.kt').

    Returns repo-relative paths.
    """
    return [
        str(p.relative_to(REPO_DIR)) for p in REPO_DIR.rglob(file_name)
        if not SKIP_DIRS.intersection(p.relative_to(REPO_DIR).parts)
    ]


def read_source_file(path: str) -> str:
    """Read a repo-relative source file. Lines are prefixed with their 1-based line numbers."""
    text = _safe(path).read_text()
    return "\n".join(f"{i}: {l}" for i, l in enumerate(text.splitlines(), 1))


def write_source_file(path: str, content: str) -> str:
    """Overwrite a repo-relative source file (.kt/.java/.kts/.xml) with the full fixed content.

    Do not include line-number prefixes in content.
    """
    p = _safe(path)
    if p.suffix not in SOURCE_SUFFIXES:
        raise ValueError(f"Only {SOURCE_SUFFIXES} files can be modified")
    p.write_text(content)
    diff = subprocess.run(["git", "diff", "--", path], cwd=REPO_DIR, capture_output=True, text=True).stdout
    return f"Wrote {path}.\n{diff}"
