# 🚀 Getting Started — Clone & Run Locally

This guide walks you through running **AI Resume Agent** on your own machine, step by step.
Everything runs locally; no paid API keys are required.

> **Time needed:** ~10–15 minutes (most of it is a one-time model download).

---

## 0. Prerequisites

You'll need these installed first:

| Tool | Version | Why |
|------|---------|-----|
| **Git** | any | to clone the repo |
| **Python** | **3.11+** | the app (3.10 or lower will NOT work) |
| **Ollama** | latest | runs the local LLM — install from <https://ollama.com> |

Check what you have:
```bash
git --version
python3 --version      # if < 3.11, install 3.11 (see Step 2)
```

---

## 1. Clone the repository

```bash
git clone <your-repo-url>
cd <repo-folder>          # e.g. cd AI-Resume-Agent  (or Resume_Project)
```

---

## 2. Install Python 3.11 (skip if you already have it)

**macOS (Homebrew):**
```bash
brew install python@3.11
```

**Ubuntu / Debian:**
```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv
```

**Windows:** download the 3.11 installer from <https://www.python.org/downloads/> and
tick **"Add Python to PATH"** during install.

---

## 3. Create a virtual environment & install dependencies

**macOS / Linux:**
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**Windows (PowerShell):**
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

Then install the browser used for JD-by-URL (JavaScript pages):
```bash
playwright install chromium
```

> You should see `(.venv)` at the start of your terminal prompt — that means the
> environment is active. Re-run the `activate` command in any new terminal.

---

## 4. Install & start the local LLM (Ollama)

1. Install Ollama from <https://ollama.com> (macOS/Windows app, or Linux script).
2. Start the Ollama server (leave this running in its own terminal):
   ```bash
   ollama serve
   ```
3. Download the default model (one time, ~5 GB):
   ```bash
   ollama pull qwen3:8b
   ```

> Want a smaller/faster model? Pull another (e.g. `ollama pull llama3.2`) and set
> `OLLAMA_MODEL` in `.env` (see Step 5).

---

## 5. (Optional) Configure settings

Defaults work out of the box. To customize:
```bash
cp .env.example .env
```
Then edit `.env` (model, page limit, etc.). Key options:
- `OLLAMA_MODEL=qwen3:8b`
- `LLM_REASONING=false`  ← keep **false** for fast generation
- `MAX_PAGES=2`

---

## 6. Run the app

With the virtual environment active **and** `ollama serve` running:
```bash
streamlit run app.py
```
It opens automatically at **http://localhost:8501** (otherwise open that URL).

**Stop the app:** press `Ctrl + C` in its terminal.
**Different port:** `streamlit run app.py --server.port 8502`

---

## 7. Use it (quick tour)

1. **Profile** — upload your master resume (PDF/DOCX) or load a saved profile; review/edit.
2. **Job Description** — paste the JD (or a URL) → **Parse & match** (auto parse → analyze → match).
3. **Confirm** — tick any job skills you genuinely have.
4. **Resume** — download the tailored **PDF** / **DOCX**.

Your profiles are saved under `storage/users/`, and generated resumes under `outputs/`.

---

## 8. Run the tests (optional)

```bash
source .venv/bin/activate      # (Windows: .\.venv\Scripts\Activate.ps1)
pytest
```
The suite uses a mocked LLM — **Ollama is not required** to run tests.

---

## 🧰 Troubleshooting

| Symptom | Fix |
|---------|-----|
| **"LLM offline"** dot / generation errors | Make sure `ollama serve` is running and `ollama pull qwen3:8b` finished. |
| `streamlit: command not found` | You didn't activate the venv — run the `activate` command from Step 3. |
| `python3.11: command not found` | Install Python 3.11 (Step 2), or use the exact path to the 3.11 binary. |
| Generation feels very slow | Ensure `LLM_REASONING=false` (default). Bigger models are slower. |
| JD **URL** won't extract | Many job boards block bots / require login — just **paste** the JD text instead. |
| Port 8501 in use | `streamlit run app.py --server.port 8502` |

---

## 🔄 Updating to the latest version

```bash
git pull
source .venv/bin/activate
pip install -r requirements.txt   # in case dependencies changed
```

---

## 🔒 A note on privacy

Everything runs on your machine. Resumes/profiles stay in local folders that are
**git-ignored** (`storage/`, `outputs/`, `logs/`, `.env`) — they are never committed or
sent anywhere.
