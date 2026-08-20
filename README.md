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

## Mobile AI integration (initial API)

The initial app integration keeps the API deliberately small:

- `POST /api/v1/users/sync` creates or retrieves the AI user and its separate Emma and Ben threads.
- `WSS /api/v1/chat` accepts a `start` event containing `external_user_id`, `persona`, and the temporary app integration key, followed by `message` events.
- `DELETE /api/v1/users/{external_user_id}` deletes the profile, both persona threads, messages, and summaries.

HTTP calls use `X-Blissiree-App-Key`. The key is supplied through the `MOBILE_API_KEY` Secret Manager environment reference and must never be committed or logged. This is a temporary integration boundary until the existing mobile login token is verified directly by the AI service.

For every socket message the server supplies Gemini with the selected persona's durable long-term summary and latest ten complete user/assistant exchanges. The final validated exchange is persisted. Summary refresh runs after the reply and is due weekly, or earlier when eight unsummarised exchanges accumulate, so it does not delay the visible response.
