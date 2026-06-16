# AIStory — local-only security notes

AIStory is designed to run **on your machine** (`127.0.0.1` by default). Treat it like a single-player game with a local save folder, not a public web service.

## Defaults

- Server binds to `127.0.0.1` unless you set `AISTORY_HOST`.
- CORS allows only local dev origins unless you set `AISTORY_CORS_ORIGINS`.
- There is **no authentication**. Anyone who can reach the server can play your save and spend your `GEMINI_API_KEY` quota.

## Do not expose publicly

Do not port-forward, tunnel, or deploy this API to the internet without adding authentication, HTTPS, rate limits, and separate per-user storage.

## Secrets

- Keep `GEMINI_API_KEY` in `.env` (gitignored), never in commits.
- Save slots under `saves/` contain full game state — treat as personal data.

## Debug endpoints

Set `AISTORY_DEBUG=1` to enable `/api/debug/*` and the world inspector. Disable in shared environments.
