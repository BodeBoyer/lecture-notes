"""
NotebookLM source pusher — Phase 2, experimental.

Uploads a generated notes Markdown file directly into a per-course
NotebookLM notebook as a new source, via the unofficial `notebooklm-py`
wrapper (browser automation — there is no public NotebookLM API for
personal Google accounts).

Best-effort: the wrapper drives internal NotebookLM endpoints that
Google can change without notice. Drive remains the reliable path.

Auth: one-time `python notebooklm_login.py` stores session cookies.
`from_storage()` reuses them on subsequent runs.

Course → notebook id mapping is read from env:
    LECTURE_NOTES_NBLM_NOTEBOOKS=COMP-210=<id>,COMP-301=<id>

Course names are canonicalized the same way `notes.py` names note
folders (uppercase, spaces and slashes → hyphens), so "COMP 210" matches
the `COMP-210=...` entry.
"""

import asyncio
import os
from pathlib import Path
from typing import Optional


def _load_env() -> None:
    env_file = Path(__file__).parent / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def _canonical_course(course: str) -> str:
    return course.strip().replace(" ", "-").replace("/", "-").upper()


def _load_notebook_map() -> dict:
    raw = os.environ.get("LECTURE_NOTES_NBLM_NOTEBOOKS", "").strip()
    out = {}
    if not raw:
        return out
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or "=" not in chunk:
            continue
        key, _, value = chunk.partition("=")
        key = _canonical_course(key)
        value = value.strip()
        if key and value:
            out[key] = value
    return out


def lookup_notebook_id(course: str) -> Optional[str]:
    return _load_notebook_map().get(_canonical_course(course))


async def _push_async(notebook_id: str, local_path: Path) -> dict:
    from notebooklm import NotebookLMClient

    async with await NotebookLMClient.from_storage() as client:
        source = await client.sources.add_file(
            notebook_id, local_path, mime_type="text/markdown"
        )
        return {
            "source_id": getattr(source, "id", None),
            "title": getattr(source, "title", local_path.name),
            "notebook_id": notebook_id,
        }


def push_to_notebook(local_path: Path, course: str) -> dict:
    """Upload a Markdown notes file as a NotebookLM source.

    Returns a result dict, or {"skipped": "<reason>"} when no notebook
    is configured for this course. Raises on actual auth/upload errors
    so callers can warn or fail as they prefer.
    """
    if not local_path.exists():
        raise FileNotFoundError(local_path)

    notebook_id = lookup_notebook_id(course)
    if not notebook_id:
        return {
            "skipped": (
                f"no notebook id mapped for course {course!r} "
                f"(canonical {_canonical_course(course)!r}). "
                f"Set LECTURE_NOTES_NBLM_NOTEBOOKS in .env."
            )
        }

    return asyncio.run(_push_async(notebook_id, local_path))


def main():
    import sys

    if len(sys.argv) != 3:
        print("Usage: python notebooklm_pusher.py <path-to-notes.md> <course>")
        sys.exit(1)

    _load_env()
    path = Path(sys.argv[1]).expanduser().resolve()
    course = sys.argv[2]

    result = push_to_notebook(path, course)
    if "skipped" in result:
        print(f"Skipped: {result['skipped']}")
        sys.exit(2)

    print(f"Added NotebookLM source: {result.get('title')}")
    print(f"  Source id  : {result.get('source_id')}")
    print(f"  Notebook id: {result.get('notebook_id')}")


if __name__ == "__main__":
    main()
