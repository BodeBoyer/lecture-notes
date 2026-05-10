"""
Replacement for `notebooklm login` — the upstream CLI is broken on Python 3.9
(uses PEP 604 union syntax). This script does the same thing, but only imports
the parts of `notebooklm-py` that are 3.9-compatible.

Auto-detects successful login by watching for Google session cookies, so it
works even when launched without an interactive stdin (e.g., via Claude Code's
`!` prefix). Sign in with the Google account you use for NotebookLM in the
browser window that opens; the script saves cookies and exits on its own.

    .venv/bin/python notebooklm_login.py

Cookies land at ~/.notebooklm/storage_state.json so subsequent uploader runs
are non-interactive.
"""

import time
from pathlib import Path

# After Google sign-in completes, these cookies appear on `.google.com`.
# `SAPISID` is reliably set after first-party auth and is what NotebookLM
# uses to authorize internal API calls. Treat its presence as proof of login.
REQUIRED_COOKIES = {"SAPISID"}
TIMEOUT_SECONDS = 5 * 60
POLL_INTERVAL = 2.0


def _has_required_cookies(cookies) -> bool:
    names = {c["name"] for c in cookies if c.get("domain", "").endswith("google.com")}
    return REQUIRED_COOKIES.issubset(names)


def main():
    try:
        from notebooklm.paths import get_storage_path, get_browser_profile_dir
    except ImportError:
        print("notebooklm-py is not installed. Run:")
        print("  .venv/bin/pip install -r requirements-nblm.txt")
        raise SystemExit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Run:")
        print("  .venv/bin/pip install -r requirements-nblm.txt")
        print("  .venv/bin/playwright install chromium")
        raise SystemExit(1)

    storage_path: Path = get_storage_path()
    browser_profile: Path = get_browser_profile_dir()
    storage_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    browser_profile.mkdir(parents=True, exist_ok=True, mode=0o700)

    print("Opening browser for Google login...")
    print(f"Persistent profile: {browser_profile}")
    print(f"Will save cookies to: {storage_path}")
    print()
    print("Sign in with your NotebookLM Google account in the Chromium window")
    print("that just opened. The script will detect successful login automatically and")
    print("close on its own (no ENTER needed). Polling every 2s, timeout 5 min.")
    print()

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(browser_profile),
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--password-store=basic",
            ],
            ignore_default_args=["--enable-automation"],
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://notebooklm.google.com/")

        deadline = time.time() + TIMEOUT_SECONDS
        last_status = ""
        while time.time() < deadline:
            cookies = context.cookies()
            if _has_required_cookies(cookies):
                print("Google auth cookies present.")
                break
            status = f"  ...waiting for login (url={page.url!r})"
            if status != last_status:
                print(status)
                last_status = status
            time.sleep(POLL_INTERVAL)
        else:
            print(f"\nTimed out after {TIMEOUT_SECONDS}s without detecting login.")
            context.close()
            raise SystemExit(1)

        # Force a fully-loaded NotebookLM page so domain-specific session
        # cookies (CSRF, etc.) get issued. Without this, the saved storage
        # is missing the notebooklm.google.com cookies that the library's
        # fetch_tokens() requires, and uploads fail with "Authentication
        # expired or invalid."
        print("Loading NotebookLM home to capture session cookies...")
        page.goto("https://notebooklm.google.com/", wait_until="networkidle")
        # Best-effort settle so any deferred cookie writes complete.
        time.sleep(2.0)

        nblm_cookies = [c for c in context.cookies() if "notebooklm" in c.get("domain", "")]
        if not nblm_cookies:
            print(
                "Warning: no notebooklm.google.com cookies were issued. "
                "Saving anyway, but the upload may still fail."
            )

        context.storage_state(path=str(storage_path))
        storage_path.chmod(0o600)
        context.close()

    print(f"\nAuthentication saved to: {storage_path}")


if __name__ == "__main__":
    main()
