# Automatic LinkedIn publishing after DEV.to

The DEV.to workflow publishes approved Markdown, captures the actual DEV.to slug, and builds `https://www.sanukhan.dev/blog/<slug>`. It generates a LinkedIn draft and (once configured) automatically posts it to the authenticated member's LinkedIn feed.

## LinkedIn setup

1. Create an application at https://www.linkedin.com/developers/apps and associate it with an eligible LinkedIn Page if requested.
2. In **Products**, request **Share on LinkedIn**. In **Auth**, verify the `w_member_social` scope is available for the application. Access is subject to LinkedIn's product and permission approval.
3. In **Auth**, register your HTTPS OAuth redirect URL. Copy the app's **Client ID** and **Client Secret** into your secure credential store; do not commit them to Git.
4. Complete LinkedIn's **3-legged authorization code** flow for your own account, requesting `w_member_social`. Exchange the authorization code for an access token using `https://www.linkedin.com/oauth/v2/accessToken`. The authorization code is short-lived and single-use.
5. Obtain the authenticated member's **Person URN** (`urn:li:person:<id>`) using an identity/profile API permitted for your app. Do not assume your public profile URL's vanity name is the Person ID.
6. In GitHub repository **Settings → Environments → devto-production**, configure:
   - Secret: `LINKEDIN_ACCESS_TOKEN` — authorized access token with `w_member_social`.
   - Variable: `LINKEDIN_AUTHOR_URN` — authenticated member's Person URN.
   - Optional variable: `LINKEDIN_API_VERSION` — supported version in `YYYYMM` format (default `202607`; update as LinkedIn sunsets API versions).
   - Existing DEV.to secret: `DEVTO_API_KEY`.
7. Confirm GitHub Actions can write repository contents (the workflow grants `contents: write`). The branch `automation/linkedin-publication-ledger` and its `linkedin-publication-ledger.json` file must exist and permit writes by GitHub Actions.

**Do not place LinkedIn tokens in Markdown, pull requests, GitHub Actions logs, or repository variables.** GitHub environment secrets are read only during the publishing job.

## Behavior and safety

- LinkedIn posting only runs after successful DEV.to publishing, and uses the returned DEV.to slug.
- The text includes the portfolio URL, not the DEV.to URL.
- The workflow generates downloadable drafts and a GitHub Actions summary.
- Posts are created with `POST https://api.linkedin.com/rest/posts` and `lifecycleState: PUBLISHED`.
- A persistent GitHub ledger prevents duplicate posts for the same LinkedIn author and slug, including `publish-all` reruns.
- A ledger entry is reserved as `pending` **before** the external LinkedIn POST. If LinkedIn succeeds but its response is lost, reruns will skip rather than risk duplicate public posts. Inspect LinkedIn manually and reconcile the ledger before attempting again.
- Updating an existing DEV.to article does not repost the same slug.
- If LinkedIn credentials are absent, the workflow warns and skips LinkedIn, while DEV.to still succeeds.
- If LinkedIn rejects the post, the LinkedIn stage fails but the prior DEV.to publication remains published.

## Token expiration

LinkedIn member access tokens commonly expire after 60 days. Programmatic refresh tokens are available only for approved LinkedIn Marketing Developer Platform partners; do not assume your application receives one. Reauthorize and update `LINKEDIN_ACCESS_TOKEN` before expiry unless you have a separately approved token renewal integration.

## Backfill already-published articles

After merging, **Actions → DEV.to publishing → Run workflow → publish-all** re-syncs approved articles and generates LinkedIn posts for slugs not already recorded in the ledger. **This is a public-posting operation**, potentially creating posts for *every* approved article. To avoid a mass backfill, instead publish a single newly approved article through the standard merge workflow, or pre-populate the ledger for existing articles after verifying their LinkedIn publication state.

Reference: https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api
