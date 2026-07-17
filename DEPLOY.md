# Deploying CV Checker (all free tiers)

One container serves both the API and the built frontend — a single public URL.
Total cost: $0.

## 0. Prerequisites (one-time, ~15 min, all free)

1. **GitHub repo** — push this project (Render and HF Spaces deploy from GitHub).
2. **Qdrant Cloud** — https://cloud.qdrant.io → create a free 1 GB cluster →
   note the cluster URL and API key.
3. Your existing **Gemini** and **Langfuse** keys from `backend/.env`.

## 1. Environment variables (same set everywhere)

| var | value |
|---|---|
| `GOOGLE_API_KEY` | your Gemini key |
| `QDRANT_URL` | Qdrant Cloud cluster URL (`https://xyz.cloud.qdrant.io:6333`) |
| `QDRANT_API_KEY` | Qdrant Cloud key |
| `DATABASE_URL` | Neon/Supabase Postgres connection string (profiles + sessions persist across restarts) |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Langfuse project keys |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` |
| `PORT` | `7860` on HF Spaces; leave default elsewhere (Render sets it) |

## 2A. Deploy on Render (recommended: simplest)

1. https://render.com → New → **Web Service** → connect the GitHub repo.
2. Runtime: **Docker** (it finds the Dockerfile automatically).
3. Instance type: **Free**.
4. Add the environment variables above → Deploy.
5. Health check path: `/health`.
6. **Memory (important)**: the free instance has 512 MB, which does not fit the
   embedding model + cross-encoder reranker together — the first chat request
   OOMs. Add `RERANK=false`: hybrid-only retrieval still scores 100%
   section-hit@5 and 0.95 MRR on the gold set (vs 0.98 with rerank), so this is
   a measured trade-off, not a downgrade. For the full pipeline including the
   reranker, use Hugging Face Spaces (16 GB) instead — section 2B.

## 2B. Or: Hugging Face Spaces (no longer free)

As of mid-2026, HF moved **Docker SDK Spaces to paid** (Pro, ~$9/mo); the free
Space types (Gradio/Static) cannot run this container. If on Pro: create a
Docker Space, push the repo (README already carries the Space metadata), and add
the env vars as Secrets — the full pipeline runs comfortably in 16 GB, so omit
`RERANK`.

## 3. Seed the deployed app

Open `https://<your-url>/` and drag the sample CVs from `data/sample_cvs/` into the
Upload page (Gemini profile extraction runs per file, so give it ~1 min per batch).
Ingestion is idempotent — re-uploading a file replaces it.

## 4. (Optional) Split frontend onto Vercel

Only if you want the frontend on its own URL; the single container already serves it.

1. Vercel → Import repo → root directory `frontend`.
2. Env var `VITE_API_BASE=https://<backend-url>` (no trailing slash).
3. On the backend service, set `ALLOWED_ORIGINS=https://<vercel-url>`.

## Local container run (verification)

```bash
podman build -t cv-checker .
podman run --rm -p 8080:8000 --env-file backend/.env \
  -e QDRANT_URL=http://host.containers.internal:6333 cv-checker
# open http://localhost:8080
```

## Known free-tier constraints

- **Cold starts**: free Render/HF instances sleep when idle; first request after a
  nap takes ~30-60 s (models are pre-baked into the image, so it's process start,
  not downloads). Mention it in the README so demo visitors aren't surprised.
- **State survives restarts**: chunks live in Qdrant Cloud and profiles/sessions in
  Neon Postgres, so the container is stateless — restarts and redeploys lose nothing.
  (Without `DATABASE_URL` it falls back to in-container SQLite, which is ephemeral.)
- **Workspaces**: visitor uploads land in anonymous per-browser workspaces; the shared
  demo corpus is read-only (uploads to it require `ALLOW_DEMO_WRITES=true`, used only
  for seeding).
- **Gemini free tier**: `gemini-3.1-flash-lite` allows 500 requests/day. Each chat
  costs 2 calls (router + answer); each uploaded CV costs 1. Fine for a demo, and
  the app returns a clean 429 message when the quota is hit.
