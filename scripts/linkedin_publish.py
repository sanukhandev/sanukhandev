#!/usr/bin/env python3
"""Publish confirmed DEV.to articles to LinkedIn once, using a GitHub ledger."""
import base64
import json
import os
from pathlib import Path
import re
import sys
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from linkedin_drafts import draft

LEDGER_BRANCH = "automation/linkedin-publication-ledger"
LEDGER_PATH = "linkedin-publication-ledger.json"


def request_json(method, url, token, data=None, headers=None):
    request = Request(
        url,
        data=None if data is None else json.dumps(data).encode("utf-8"),
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json" if "api.github.com" in url else "application/json",
            "Content-Type": "application/json",
            "User-Agent": "sanukhandev-devto-linkedin-publisher",
            **(headers or {}),
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            return (json.loads(raw) if raw else {}, dict(response.headers), response.status)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"API request failed ({error.code}): {detail}") from error


def ledger_url():
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("Invalid GITHUB_REPOSITORY")
    return f"https://api.github.com/repos/{repo}/contents/{LEDGER_PATH}"


def read_ledger(token):
    url = ledger_url() + "?ref=" + quote(LEDGER_BRANCH)
    result, _, _ = request_json("GET", url, token)
    content = base64.b64decode(result["content"]).decode("utf-8")
    records = json.loads(content)
    if not isinstance(records, dict):
        raise ValueError("Invalid LinkedIn ledger")
    return records, result["sha"]


def save_ledger(token, records, sha):
    encoded = base64.b64encode(
        (json.dumps(records, indent=2, sort_keys=True) + "\n").encode("utf-8")
    ).decode("ascii")
    result, _, _ = request_json("PUT", ledger_url(), token, {
        "message": "chore: record LinkedIn publication status",
        "branch": LEDGER_BRANCH,
        "sha": sha,
        "content": encoded,
    })
    return result["content"]["sha"]


def post_linkedin(record, token, author, version):
    payload = {
        "author": author,
        "commentary": draft(record),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    _, headers, status = request_json(
        "POST", "https://api.linkedin.com/rest/posts", token, payload,
        headers={
            "Linkedin-Version": version,
            "X-Restli-Protocol-Version": "2.0.0",
        },
    )
    if status != 201:
        raise RuntimeError(f"Unexpected LinkedIn status: {status}")
    urn = next((v for k, v in headers.items() if k.lower() == "x-restli-id"), None)
    if not urn or not re.fullmatch(r"urn:li:(?:share|ugcPost):\d+", urn):
        raise RuntimeError("LinkedIn succeeded without a recognized post URN; inspect manually")
    return urn


def main():
    if len(sys.argv) != 2:
        raise ValueError("Usage: linkedin_publish.py MANIFEST_JSON")
    records = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if not records:
        print("No confirmed DEV.to articles to share.")
        return
    github_token = os.environ["GITHUB_TOKEN"]
    linkedin_token = os.environ["LINKEDIN_ACCESS_TOKEN"]
    author = os.environ["LINKEDIN_AUTHOR_URN"]
    version = os.environ.get("LINKEDIN_API_VERSION") or "202607"
    if not re.fullmatch(r"urn:li:person:[A-Za-z0-9_-]+", author):
        raise ValueError("LINKEDIN_AUTHOR_URN must be a valid person URN")
    if not re.fullmatch(r"20\d{4}", version):
        raise ValueError("LINKEDIN_API_VERSION must be YYYYMM")
    ledger, sha = read_ledger(github_token)
    for record in records:
        slug = record["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Invalid slug: {slug!r}")
        if record["portfolio_url"] != f"https://www.sanukhan.dev/blog/{slug}":
            raise ValueError("Invalid portfolio URL")
        key = f"{author}/{slug}"
        if key in ledger:
            print(f"SKIP LinkedIn already processed: {slug} ({ledger[key]['status']})")
            continue
        # Reserve before POST. If the response is lost, reruns will NOT
        # double-post. A pending entry requires manual reconciliation.
        ledger[key] = {"status": "pending", "portfolio_url": record["portfolio_url"]}
        sha = save_ledger(github_token, ledger, sha)
        urn = post_linkedin(record, linkedin_token, author, version)
        ledger[key] = {
            "status": "published",
            "portfolio_url": record["portfolio_url"],
            "linkedin_urn": urn,
        }
        sha = save_ledger(github_token, ledger, sha)
        post_url = f"https://www.linkedin.com/feed/update/{quote(urn, safe=':')}/"
        print(f"LINKEDIN PUBLISHED: {slug} -> {post_url}")
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as handle:
                handle.write(f"\nLinkedIn published: {record['portfolio_url']} — {post_url}\n")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
