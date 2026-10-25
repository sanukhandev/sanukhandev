#!/usr/bin/env python3
"""Generate LinkedIn drafts from confirmed DEV.to publication results."""
import json
import os
from pathlib import Path
import re
import sys


def draft(record):
    title = record["title"]
    url = record["portfolio_url"]
    if title == "Your Code Isn't Clean If Someone Has to Decode It":
        return (
            "Your code can pass every test and still be difficult to maintain.\n\n"
            "If the next engineer needs to decode variable names before understanding "
            "the business rule, there's a readability problem worth fixing.\n\n"
            "Across production platforms, APIs, and integrations, I've learned that "
            "clarity is more than a style preference. It helps reviewers spot incorrect "
            "assumptions and makes handovers less painful.\n\n"
            "In my latest article, I share practical JavaScript and TypeScript examples "
            "covering intention-revealing names, business rules, and code reviews.\n\n"
            "Read the article: " + url + "\n\n"
            "What's one naming habit that has made your codebase easier to maintain?\n\n"
            "#SoftwareEngineering #CleanCode #TypeScript #CodeReview"
        )
    return (
        f"Good engineering is about making complex decisions easier to understand.\n\n"
        f"I've published a new article: {title}\n\n"
        "It explores practical engineering choices and the trade-offs that matter "
        "when teams build and maintain real-world systems.\n\n"
        f"Read it here: {url}\n\n"
        "Which approach has worked best in your projects?\n\n"
        "#SoftwareEngineering #SoftwareArchitecture #EngineeringLeadership"
    )


def generate(manifest_path, output_dir):
    records = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    sections = []
    for record in records:
        slug = record["slug"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
            raise ValueError(f"Unsafe slug: {slug!r}")
        expected = f"https://www.sanukhan.dev/blog/{slug}"
        if record["portfolio_url"] != expected:
            raise ValueError("Portfolio URL does not match the published slug")
        post = draft(record)
        (output_dir / f"{slug}-linkedin.md").write_text(post + "\n", encoding="utf-8")
        sections.append(
            f"### {record['title']}\n\n"
            f"DEV.to: {record['devto_url']}\n\n"
            f"Portfolio: {expected}\n\n"
            f"LinkedIn draft:\n\n{post}\n"
        )
        print(f"LINKEDIN DRAFT: {output_dir / (slug + '-linkedin.md')}")
    if summary_path and sections:
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write("## Published articles and LinkedIn drafts\n\n")
            handle.write("\n---\n\n".join(sections) + "\n")
    if not records:
        print("No new or updated DEV.to articles; no LinkedIn drafts generated.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: linkedin_drafts.py MANIFEST_JSON OUTPUT_DIR")
    generate(sys.argv[1], Path(sys.argv[2]))
