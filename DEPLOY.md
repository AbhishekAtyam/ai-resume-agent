# ☁️ Deploy for Free — Streamlit Community Cloud + Groq

This guide deploys the app publicly, **for free**, on **Streamlit Community Cloud**.

---

## How the app is structured (important)

- **There is no separate frontend/backend.** This is a **single Streamlit app**: `app.py`
  is the web UI *and* it runs all the Python logic (`agents/`, `graph/`, `tools/`,
  `models/`) in the **same process**. So you deploy **one** web service — not two.
- **The app auto-picks an LLM** (`LLM_PROVIDER=auto`) in this order: **Ollama → Gemini →
  Groq** — it uses the first one available. On your machine it finds **Ollama** (fully local,
  private). Free hosts can't run Ollama (needs ~5–8 GB RAM + a daemon), so on the cloud it
  automatically falls back to **Gemini** (recommended, free) — or Groq if you provide that
  key instead. This is just config; your local setup is unchanged.

> ⚠️ **Privacy note:** in the deployed (Gemini/Groq) version, resume + JD text is sent to
> that provider's API for processing. It stays 100% local only when *you* run it on your own
> machine with Ollama. Don't put other people's private data into the public demo.

---

## Step 1 — Get a free Gemini API key (recommended)

1. Go to **<https://aistudio.google.com/app/apikey>** and sign in with your Google account.
2. Click **Create API key** and copy it.
3. Default model is `gemini-2.0-flash` (fast, free tier). You can change `GEMINI_MODEL` later.

> Prefer Groq instead? Get a key at **<https://console.groq.com>** (`gsk_...`) and set
> `GROQ_API_KEY` + `GROQ_MODEL` in Step 4 rather than the Gemini ones. The app's `auto`
> mode uses whichever key you provide.

---

## Step 2 — Push your code to GitHub

If you haven't already (see `SETUP.md` / `README.md`):
```bash
git init
git add .
git status          # confirm NO files under storage/ outputs/ logs/ and no .env/secrets.toml
git commit -m "AI Resume Agent"
git branch -M main
git remote add origin <your-repo-url>
git push -u origin main
```
The repo must be on GitHub (public is simplest for the free tier).

---

## Step 3 — Create the app on Streamlit Community Cloud

1. Go to **<https://share.streamlit.io>** and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub.**
3. Select your **repository**, **branch** (`main`), and set **Main file path** to `app.py`.
4. (Optional) Set a custom app URL.
5. Don't click Deploy yet — add secrets first (next step), or deploy then add secrets and reboot.

---

## Step 4 — Add your secrets

In the app's **Settings → Secrets**, paste (from `.streamlit/secrets.toml.example`), using
your real key:

```toml
LLM_PROVIDER = "auto"
GEMINI_API_KEY = "your_gemini_key_here"
GEMINI_MODEL = "gemini-2.0-flash"
ENABLE_PLAYWRIGHT = "false"
LLM_REASONING = "false"
```

> Using Groq instead? Replace the two `GEMINI_*` lines with
> `GROQ_API_KEY` / `GROQ_MODEL`.

Save. Streamlit exposes these to the app automatically. With `auto`, the cloud app finds no
Ollama and uses your Gemini (or Groq) key.

---

## Step 5 — Deploy & verify

1. Click **Deploy** (or **Reboot** if you deployed before adding secrets). First build
   installs `requirements.txt` (a few minutes).
2. When it opens, the top bar shows **🟢 LLM: gemini** (the key is set and active).
3. Test end-to-end: **Profile** (upload or load) → **Job Description** → *paste a JD* →
   **Parse & match** → **Confirm** → **Generate** → download PDF/DOCX.

---

## Caveats on the free tier (please read)

- **Storage is ephemeral.** Streamlit Cloud resets the filesystem on reboot/update, so
  **saved profiles and generated files don't persist** across restarts. Fine for a demo
  (upload each session); for persistence you'd add a database/cloud bucket later.
- **Sleeps when idle.** Free apps spin down after inactivity and take a few seconds to wake.
- **Free-tier rate limits.** Gemini/Groq free tiers limit requests/tokens per minute.
  Generation makes several LLM calls (and up to 3 correction attempts), so under heavy use
  you may hit limits — a lighter model (e.g. Gemini `gemini-2.0-flash`, Groq
  `llama-3.1-8b-instant`) helps.
- **URL scraping is limited.** `ENABLE_PLAYWRIGHT=false` on the host means JS-heavy job
  pages won't auto-extract — **pasting the JD always works** and is the reliable path.
- **~1 GB RAM.** Plenty for this app with a hosted LLM (no local model in memory).

---

## Other free options (quick notes)

- **Hugging Face Spaces (Streamlit SDK)** — free, more RAM (16 GB). Same idea: push the repo
  as a Space, add `GROQ_API_KEY` etc. as Space **secrets**. Good alternative.
- **Render (free web service)** — works but sleeps + low RAM; set the start command to
  `streamlit run app.py --server.port $PORT --server.address 0.0.0.0` and add the env vars.
- **Google Cloud Run** — has a small free tier but requires **billing enabled + a Docker
  image**; more setup than the above.
- **"Google AI Studio" is NOT hosting** — it's a Gemini prompt playground, not a place to
  deploy a web app.

---

## Keeping it truly private

If you don't want any data leaving your machine, **don't deploy publicly** — run it locally
with Ollama (see `SETUP.md`). You can still share the **code** so others run their own
local copy.
