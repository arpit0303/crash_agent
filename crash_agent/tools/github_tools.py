import os
import re
import subprocess
import time

import jwt
import requests
from github import Auth, Github

from .code_tools import REPO_DIR

API = "https://api.github.com"


def _repo_slug() -> str:
    slug = os.getenv("GITHUB_REPO")
    if slug:
        return slug
    url = subprocess.run(["git", "remote", "get-url", "origin"], cwd=REPO_DIR, capture_output=True, text=True, check=True).stdout
    return re.search(r"[:/]([^/:]+/[^/]+?)(?:\.git)?$", url.strip()).group(1)


def _token() -> str:
    """GitHub App installation token, falling back to GITHUB_TOKEN."""
    app_id, key_path = os.getenv("GITHUB_APP_ID"), os.getenv("GITHUB_APP_PRIVATE_KEY_PATH")
    if not (app_id and key_path):
        if os.getenv("GITHUB_TOKEN"):
            return os.environ["GITHUB_TOKEN"]
        raise RuntimeError("Set GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY_PATH (or GITHUB_TOKEN) in .env")
    now = int(time.time())
    app_jwt = jwt.encode({"iat": now - 60, "exp": now + 540, "iss": app_id}, open(key_path).read(), algorithm="RS256")
    h = {"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"}
    inst = os.getenv("GITHUB_APP_INSTALLATION_ID")
    if not inst:
        r = requests.get(f"{API}/repos/{_repo_slug()}/installation", headers=h)
        r.raise_for_status()
        inst = r.json()["id"]
    r = requests.post(f"{API}/app/installations/{inst}/access_tokens", headers=h)
    r.raise_for_status()
    return r.json()["token"]


def _git(*args, check=True):
    return subprocess.run(["git", *args], cwd=REPO_DIR, capture_output=True, text=True, check=check)


def create_fix_pull_request(branch_name: str, commit_message: str, pr_title: str, pr_body: str) -> str:
    """Commit the current working-tree changes of the target repo to a new branch, push it and open a GitHub PR.

    Args:
        branch_name: New branch name, e.g. 'fix/crashlytics-30cad547-npe'.
        commit_message: Commit message.
        pr_title: Pull request title.
        pr_body: Pull request description (crash summary, root cause, fix).

    Returns:
        The URL of the created pull request.
    """
    if not _git("status", "--porcelain").stdout.strip():
        return "No changes to commit."
    slug, token = _repo_slug(), _token()
    base = _git("symbolic-ref", "--short", "HEAD").stdout.strip()
    if base == branch_name:
        raise ValueError("Branch name must differ from the current branch")
    _git("checkout", "-b", branch_name)
    try:
        _git("add", "-A", "--", "app/src")
        _git("-c", "user.name=Crash Fix AI", "-c", "user.email=crash-fix-ai@users.noreply.github.com",
             "commit", "-m", commit_message)
        _git("push", f"https://x-access-token:{token}@github.com/{slug}.git", f"{branch_name}:{branch_name}")
        pr = Github(auth=Auth.Token(token)).get_repo(slug).create_pull(
            title=pr_title, body=pr_body, head=branch_name, base=base)
    finally:
        _git("checkout", base, check=False)
    return pr.html_url
