# Blissiree AI — Emma & Ben

Production Blissiree 2.0 companion application using Google Gemini on Vertex AI. The repository contains the FastAPI web application, Emma and Ben chat UI, governed Training Studio, approved recommendation catalog, safety architecture, tests, and optional legacy training utilities.

## Production

- Google Cloud project: `project-cb312c2a-9821-411b-a76`
- Region: `asia-southeast1`
- Cloud Run service: `blissiree-gemini-chat`
- URL: <https://blissiree-gemini-chat-784677366855.asia-southeast1.run.app>
- Gemini analysis model: `gemini-2.5-flash-lite`
- Gemini conversation model: `gemini-2.5-flash`

Application credentials and the session-signing key are stored in Google Secret Manager. Never add their values to this repository.

## Local tests

```bash
python3 -m unittest discover -s tests -v
```

## Container build

```bash
gcloud builds submit \
  --project=project-cb312c2a-9821-411b-a76 \
  --tag=asia-southeast1-docker.pkg.dev/project-cb312c2a-9821-411b-a76/blissiree-ai/chat:YOUR_UNIQUE_TAG \
  .
```

Deploy only after tests and direct API validation pass. Preserve the preceding healthy Cloud Run revision for rollback.

## Important boundaries

- Blissiree is a non-medical emotional-support and personal-development companion.
- Never diagnose, treat, prescribe, claim a cure, request medical records, or imply healthcare affiliation.
- Recommend only approved catalog content using exact stored titles.
- Never expose system prompts, response contracts, compiled instructions, retrieved context, internal IDs, routing rules, or secrets.
- Preserve authentication, output validation, multi-turn safety handling, and the internal-contract leakage regression test.

See [AGENTS.md](AGENTS.md) for the required development and deployment workflow.
