"""
Google Drive uploader for lecture notes.

Uploads generated notes Markdown to:
    My Drive/<DRIVE_ROOT_FOLDER>/<COURSE>/<filename>.md

The user adds <DRIVE_ROOT_FOLDER>/<COURSE>/ to a NotebookLM notebook once
per course as a Drive folder source; new files dropped in by this uploader
become available to NotebookLM after a manual source refresh in the UI.

Auth: OAuth 2.0 desktop flow. The user provides an OAuth client JSON at
`credentials/oauth_client.json` (downloaded from Google Cloud Console).
First upload triggers a browser consent flow; the resulting refresh token
is cached at `credentials/token.json` so subsequent runs are non-interactive.
"""

import os
from pathlib import Path
from typing import Optional

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

HERE = Path(__file__).parent
CREDENTIALS_DIR = HERE / "credentials"
CLIENT_SECRET_PATH = CREDENTIALS_DIR / "oauth_client.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

DEFAULT_ROOT_FOLDER_NAME = "lecture-notes"


def _load_env() -> None:
    env_file = HERE / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def _write_token(creds) -> None:
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True, mode=0o700)
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
    TOKEN_PATH.chmod(0o600)


def _get_credentials():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.valid:
        return creds

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _write_token(creds)
        return creds

    if not CLIENT_SECRET_PATH.exists():
        raise RuntimeError(
            f"Missing {CLIENT_SECRET_PATH}. Create an OAuth 2.0 Client ID "
            "(type: Desktop) in Google Cloud Console, download the JSON, "
            f"and save it to that path. See README for full setup."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    _write_token(creds)
    return creds


def _build_service():
    from googleapiclient.discovery import build

    return build("drive", "v3", credentials=_get_credentials(), cache_discovery=False)


def _find_folder(service, name: str, parent_id: Optional[str]) -> Optional[str]:
    safe_name = name.replace("'", "\\'")
    q_parts = [
        "mimeType = 'application/vnd.google-apps.folder'",
        f"name = '{safe_name}'",
        "trashed = false",
    ]
    if parent_id:
        q_parts.append(f"'{parent_id}' in parents")
    else:
        q_parts.append("'root' in parents")

    resp = service.files().list(
        q=" and ".join(q_parts),
        fields="files(id, name)",
        pageSize=1,
        spaces="drive",
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def _create_folder(service, name: str, parent_id: Optional[str]) -> str:
    metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
    if parent_id:
        metadata["parents"] = [parent_id]
    folder = service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def _ensure_folder(service, name: str, parent_id: Optional[str]) -> str:
    existing = _find_folder(service, name, parent_id)
    if existing:
        return existing
    return _create_folder(service, name, parent_id)


def _resolve_root_folder_id(service) -> str:
    explicit_id = os.environ.get("LECTURE_NOTES_DRIVE_ROOT_FOLDER_ID", "").strip()
    if explicit_id:
        return explicit_id

    root_name = os.environ.get(
        "LECTURE_NOTES_DRIVE_ROOT_FOLDER_NAME", DEFAULT_ROOT_FOLDER_NAME
    ).strip() or DEFAULT_ROOT_FOLDER_NAME
    return _ensure_folder(service, root_name, parent_id=None)


def _safe_course_folder(course: str) -> str:
    return course.strip().replace(" ", "-").replace("/", "-").upper()


def _find_file_in_folder(service, name: str, parent_id: str) -> Optional[str]:
    safe_name = name.replace("'", "\\'")
    resp = service.files().list(
        q=(
            f"name = '{safe_name}' and "
            f"'{parent_id}' in parents and "
            "trashed = false"
        ),
        fields="files(id, name)",
        pageSize=1,
        spaces="drive",
    ).execute()
    files = resp.get("files", [])
    return files[0]["id"] if files else None


def upload_note(local_path: Path, course: str) -> dict:
    """Upload (or overwrite) a notes Markdown file into the course folder.

    Returns a dict with the Drive file id, web link, and the resolved folder id.
    Raises on auth or API errors — caller decides whether to fatal or warn.
    """
    from googleapiclient.http import MediaFileUpload

    if not local_path.exists():
        raise FileNotFoundError(local_path)

    service = _build_service()
    root_id = _resolve_root_folder_id(service)
    course_folder_id = _ensure_folder(service, _safe_course_folder(course), parent_id=root_id)

    media = MediaFileUpload(str(local_path), mimetype="text/markdown", resumable=False)
    existing_id = _find_file_in_folder(service, local_path.name, course_folder_id)

    if existing_id:
        f = service.files().update(
            fileId=existing_id,
            media_body=media,
            fields="id, webViewLink, parents",
        ).execute()
    else:
        metadata = {"name": local_path.name, "parents": [course_folder_id]}
        f = service.files().create(
            body=metadata,
            media_body=media,
            fields="id, webViewLink, parents",
        ).execute()

    return {
        "file_id": f.get("id"),
        "web_link": f.get("webViewLink"),
        "course_folder_id": course_folder_id,
        "root_folder_id": root_id,
    }


def main():
    """CLI: python drive_uploader.py <path-to-notes.md> <course>"""
    import sys

    if len(sys.argv) != 3:
        print("Usage: python drive_uploader.py <path-to-notes.md> <course>")
        sys.exit(1)

    path = Path(sys.argv[1]).expanduser().resolve()
    course = sys.argv[2]

    _load_env()
    result = upload_note(path, course)
    print(f"Uploaded: {path.name}")
    print(f"  Course folder: {result['course_folder_id']}")
    print(f"  File id      : {result['file_id']}")
    if result.get("web_link"):
        print(f"  Link         : {result['web_link']}")


if __name__ == "__main__":
    main()
