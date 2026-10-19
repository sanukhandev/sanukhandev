# DEV.to publishing via GitHub Actions

This repository publishes approved Markdown articles to [DEV.to](https://dev.to/sanukhandev)
using the official Forem REST API.

## One-time configuration

1. Generate a DEV API key at https://dev.to/settings/extensions (label: GitHub Publisher).
2. Open repository **Settings → Environments → New environment**. Name it `devto-production`.
3. In that environment, select **Add secret** and store the key as `DEVTO_API_KEY`.
   Never commit the API key or paste it into an issue, PR, chat, or workflow YAML.
4. In repository **Settings → Rules → Rulesets** (or branch protection rules),
   protect `main`: require pull requests, at least one approving review, and
   successful **Validate Markdown articles** checks; restrict bypass permissions.
   Require review for changes to publisher scripts and workflows as well.
5. In the GitHub **Actions** tab, check that Actions are permitted.
6. Merge this setup PR only after steps 2–5. The workflow will not create a post
   until a merged `posts/**/*.md` file has `published: true`.

## Authoring and approval

Create a Markdown file under `posts/`, including YAML front matter:

```yaml
---
title: "How I Designed a Multi-Tenant RAG Architecture"
description: "Lessons from building a secure retrieval-augmented generation platform."
tags: [architecture, ai, python, programming]
published: false
# main_image: https://example.com/my-image.jpg
# series: Engineering Notes
# canonical_url: https://www.sanukhan.dev/original-article
---
```

Write the article below the front matter. Open a PR to validate and review it.
Set `published: true` in the PR when ready. Merge to `main` to publish it.

- Pull requests validate posts without exposing the DEV.to API secret.
- A push to `main` containing article changes runs the publisher.
- `published: false` files are ignored (not sent to DEV.to).
- Subsequent changes to a published article update the same DEV.to post.
- Publication does not delete or unpublish DEV.to posts when a file is removed.
- To re-sync every `published: true` article, run **DEV.to publishing** manually
  from the Actions tab via **Run workflow**.
- Cover images must already be reachable at an HTTPS URL.
- If cross-posting an article originally published on your own site, set
  `canonical_url` to the public original; otherwise omit it.

## Duplicate prevention and security

The publisher appends an invisible source marker to the Markdown stored on DEV.to.
It uses the marker to identify its own existing articles before creating or
updating a post. This prevents normal workflow reruns from making duplicate posts
without writing DEV.to IDs back to protected branches. An article moved to a new
path is considered a *new article*, so keep post filenames stable after publishing.

The action uses read-only GitHub permissions. The secret is provided only to the
publish job, which runs on pushes to `main` or manually; it is not given to PR
validation. The `devto-production` environment has no reviewers by default;
add required reviewers there only if you prefer manual authorization per run
instead of fully automatic publication.

This example is intentionally linked to the DEV.to account `sanukhandev`.
The action verifies the API key belongs to that account before any publishing.
GitHub branch protections/rulesets must be enabled separately: this PR alone
cannot enforce that every main-branch change received approval.

For API details, see https://developers.forem.com/api/v1.
