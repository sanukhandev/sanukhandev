#!/usr/bin/env python3
"""Publish approved Markdown posts to DEV.to without committing credentials or IDs."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

API_ROOT = "https://dev.to/api"
POST_DIR = Path("posts")
TAG = re.compile(r"^[a-z0-9]+$")
FRONT = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", re.S)


def read_post(path):
    data = path.read_text(encoding="utf-8")
    match = FRONT.match(data)
    if not match:
        raise ValueError(f"{path}: expected YAML front matter enclosed by ---")
    meta = yaml.safe_load(match.group(1))
    if not isinstance(meta, dict):
        raise ValueError(f"{path}: front matter must be a mapping")
    title = meta.get("title")
    published = meta.get("published", False)
    tags = meta.get("tags", [])
    if not isinstance(title, str) or not title.strip():
        raise ValueError(f"{path}: title is required")
    if type(published) is not bool:
        raise ValueError(f"{path}: published must be true or false")
    if not isinstance(tags, list) or not 1 <= len(tags) <= 4:
        raise ValueError(f"{path}: tags must be a list of 1–4 items")
    if any(not isinstance(t, str) or not TAG.fullmatch(t) for t in tags):
        raise ValueError(f"{path}: tags must contain only lowercase letters and digits")
    for field in ("description", "main_image", "canonical_url", "series"):
        value = meta.get(field)
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{path}: {field} must be a string")
    if published and not match.group(2).strip():
        raise ValueError(f"{path}: published article body must not be empty")
    for field in ("main_image", "canonical_url"):
        value = meta.get(field)
        if value and not value.startswith("https://"):
            raise ValueError(f"{path}: {field} must be an HTTPS URL")
    return meta, match.group(2).strip() + "\n"


def all_posts():
    return sorted(POST_DIR.rglob("*.md")) if POST_DIR.is_dir() else []


def changed_posts():
    before = os.environ.get("PUSH_BEFORE", "")
    after = os.environ.get("GITHUB_SHA", "")
    if not before or set(before) == {"0"} or not after:
        return all_posts()
    names = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=AMR", before, after, "--", "posts/"],
        text=True,
    ).splitlines()
    return sorted(Path(name) for name in names
                  if name.startswith("posts/") and name.endswith(".md") and Path(name).is_file())


def marker_for(path):
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not repo or not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise ValueError("GITHUB_REPOSITORY must be an owner/repository name")
    return "<!-- devto-source: " + repo + "/" + path.as_posix() + " -->"


class Devto:
    def __init__(self):
        self.key = os.environ.get("DEVTO_API_KEY")
        if not self.key:
            raise ValueError("DEVTO_API_KEY must be configured in GitHub Actions secrets")
        self.index = None
        self.details = {}

    def call(self, method, path, article=None):
        raw = None if article is None else json.dumps({"article": article}).encode("utf-8")
        request = Request(
            API_ROOT + path,
            data=raw,
            method=method,
            headers={
                "api-key": self.key,
                "Accept": "application/vnd.forem.api-v1+json",
                "Content-Type": "application/json",
                "User-Agent": "github-devto-article-publisher",
            },
        )
        for attempt in range(5):
            try:
                with urlopen(request, timeout=30) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                if (error.code == 429 or (method != 'POST' and error.code in (500, 502, 503, 504))) and attempt < 4:
                    try:
                        delay = min(60, max(1, int(error.headers.get("Retry-After", "0"))))
                    except ValueError:
                        delay = min(30, 2 ** (attempt + 1))
                    if delay == 1:
                        delay = min(30, 2 ** (attempt + 1))
                    time.sleep(delay)
                    continue
                details = error.read().decode("utf-8", errors="replace")[:300]
                raise RuntimeError(f"DEV.to API returned {error.code} for {method} {path}: {details}") from error
            except URLError as error:
                raise RuntimeError(f"Network error calling DEV.to: {error.reason}") from error
        raise RuntimeError("DEV.to API retries exhausted")

    def check_account(self):
        expected = os.environ.get("DEVTO_USERNAME")
        actual = self.call("GET", "/users/me").get("username")
        if not expected or actual != expected:
            raise ValueError(f"DEV.to account mismatch: expected {expected}, got {actual}")
        print(f"Authenticated DEV.to account: {actual}")

    def owned_articles(self):
        if self.index is None:
            self.index = []
            page = 1
            while True:
                batch = self.call("GET", f"/articles/me/all?per_page=100&page={page}")
                if not isinstance(batch, list):
                    raise RuntimeError("Unexpected DEV.to article index response")
                self.index.extend(batch)
                if len(batch) < 100:
                    break
                page += 1
        return self.index

    def detail(self, article_id):
        if article_id not in self.details:
            self.details[article_id] = self.call("GET", f"/articles/{article_id}")
        return self.details[article_id]

    def find_managed(self, marker, title):
        found = []
        index = self.owned_articles()
        # Check likely matches first, then the rest to survive article title changes.
        candidates = sorted((item for item in index if item.get("published_at") or item.get("published_timestamp")),
                            key=lambda item: item.get("title") != title)
        for item in candidates:
            detail = self.detail(item["id"])
            if marker in (detail.get("body_markdown") or ""):
                found.append(detail)
                if len(found) > 1:
                    raise RuntimeError(f"Multiple DEV.to articles use marker {marker}")
        return found[0] if found else None


def publish(paths):
    selected = []
    for path in paths:
        meta, body = read_post(path)
        if meta.get("published", False):
            selected.append((path, meta, body))
        else:
            print(f"SKIP draft: {path}")
    if not selected:
        print("No approved articles to publish.")
        return

    api = Devto()
    api.check_account()
    for path, meta, body in selected:
        marker = marker_for(path)
        final_body = body.rstrip() + "\n\n" + marker + "\n"
        payload = {
            "title": meta["title"],
            "body_markdown": final_body,
            "published": True,
            "tags": ",".join(meta["tags"]),
        }
        for field in ("description", "main_image", "canonical_url", "series"):
            if meta.get(field):
                payload[field] = meta[field]
        existing = api.find_managed(marker, meta["title"])
        if existing:
            result = api.call("PUT", f"/articles/{existing['id']}", payload)
            print(f"UPDATED: {path} -> {result.get('url')}")
            api.details[existing["id"]] = result
        else:
            result = api.call("POST", "/articles", payload)
            print(f"PUBLISHED: {path} -> {result.get('url')}")
            api.index.append(result)
            api.details[result["id"]] = result


def main():
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validate", action="store_true")
    modes.add_argument("--publish-changed", action="store_true")
    modes.add_argument("--publish-all", action="store_true")
    args = parser.parse_args()

    if args.validate:
        files = all_posts()
        for path in files:
            read_post(path)
        print(f"Validated {len(files)} article(s).")
    elif args.publish_changed:
        publish(changed_posts())
    else:
        publish(all_posts())


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
