# Test Phase Deployment

RepLayer test phase uses:

- Vercel for the Next.js frontend.
- Render for the FastAPI public API.
- Render Postgres for shared reputation state.

## API Deployment On Render

The repo includes `render.yaml`.

Render will create:

- `replayer-api`: public FastAPI web service.
- `replayer-postgres`: hosted Postgres database.

## Required Secrets

Fill these in the Render Blueprint screen:

```bash
ADMIN_API_KEY=generate-a-long-random-value
API_KEY=optional-backwards-compatible-dev-key
GENLAYER_CONTRACT_ADDRESS=0x59a8924E6E7D3A460e2154a304fCC2BEfEc3c8Dd
GENLAYER_ACCOUNT_PASSWORD=only-if-using-live-genlayer
```

For test phase, start with:

```bash
GENLAYER_MODE=mock
```

Switch to `GENLAYER_MODE=live` only after confirming the GenLayer CLI, account, password, and RPC behavior work in the hosted environment.

## Render Blueprint Link

After `render.yaml` is committed and pushed to GitHub, open:

```text
https://dashboard.render.com/blueprint/new?repo=https://github.com/ShalyX/replayer
```

Then:

1. Connect GitHub if prompted.
2. Review `replayer-api` and `replayer-postgres`.
3. Fill the secrets above.
4. Click Apply.
5. Wait for the API service to become live.
6. Open `https://YOUR_RENDER_API/health`.

## Connect Frontend To Hosted API

In Vercel, set:

```bash
NEXT_PUBLIC_API_BASE=https://YOUR_RENDER_API
NEXT_PUBLIC_API_KEY=dev-key-or-test-platform-key
```

For public demos, prefer a limited demo platform key instead of the admin key.

Redeploy the frontend after changing those environment variables.

## Production Note

The Render free plan is enough for test users, but not production. Before production, upgrade the database, add migrations, configure backups, and move long-running GenLayer work into an async queue.

