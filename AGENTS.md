# Blissiree AI agent instructions

Work on this repository as the authoritative source for the existing production application. Do not create a replacement GCP project, Cloud Run service, or parallel application unless the user explicitly requests it.

## Google Cloud target

- Project: `project-cb312c2a-9821-411b-a76`
- Region: `asia-southeast1`
- Service: `blissiree-gemini-chat`
- Artifact repository: `asia-southeast1-docker.pkg.dev/project-cb312c2a-9821-411b-a76/blissiree-ai`
- Production URL: `https://blissiree-gemini-chat-784677366855.asia-southeast1.run.app`

Use the user's authenticated `gcloud` session. Confirm the active account and project before changes. Never print or retrieve secret values unless an in-scope operation strictly requires them, and never put secrets into code, prompts, logs, commits, or chat output.

## Required workflow

1. Read this file, README.md, relevant docs, and current source before editing.
2. Check `git status` and preserve unrelated changes.
3. Inspect the active Cloud Run revision and image before deployment.
4. Make the smallest safe source change.
5. Run `python3 -m unittest discover -s tests -v` using a Python runtime with project dependencies.
6. Test JavaScript syntax and responsive UI for front-end changes.
7. Test the authenticated API directly for AI changes, including multi-turn context and internal-data leakage.
8. Build a uniquely tagged immutable image.
9. Deploy a new revision to the same Cloud Run service.
10. Confirm health, authentication, assets, API behavior, logs, output validation, and 100% traffic.
11. Report the commit, image tag, revision, production result, and rollback revision.

Never claim a build, test, deployment, or training action succeeded without direct verification.

## Product and safety requirements

Blissiree is a non-medical companion. Emma is warm, gentle, validating, and emotionally attentive. Ben is calm, grounded, and practical. Both use recent conversation context and must avoid repetitive clarification.

They must never diagnose, treat, prescribe, claim a cure, request medical records, or imply healthcare affiliation. They must not invent content. Recommendation titles must match approved catalog entries exactly.

Preserve defenses against leaking internal fields such as `response_contract`, `compiled_instructions`, `allowed_actions`, `retrieved_knowledge`, `response_limits`, `program_assessment_required`, and internal persona configuration.

The governed Training Studio persists content and versions in Google Cloud Storage. Do not delete or replace training content without explicit approval.

## Security

The whole application is authenticated. Credentials and session-signing material are Secret Manager references in Cloud Run. Never add credential values to GitHub. Do not weaken cookie security, protected API routes, Secret Manager use, or output safety validation.
