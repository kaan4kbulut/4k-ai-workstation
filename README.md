# 🚀 Nexus AI Studio

An Intelligent AI Orchestrator and Model Gateway. Manages multiple LLM providers
(cloud & local), routes tasks based on complexity, tracks quotas, and executes
sub-tasks in parallel.

> **Status:** working MVP. FastAPI backend + Streamlit dashboard + Ollama wrapper
> are verified end-to-end. Claude/Codex tiers are declared but have no wrapper yet.

## 📁 Project Structure
- `/core`: The brain of the system.
    - `dispatcher.py`: Sends prompts to registered model wrappers (single or parallel).
    - `router.py`: Picks the best model for a prompt (complexity + cost + quota).
    - `quota_manager.py`: Tracks usage limits per model in `data/quotas.json`.
    - `planner.py`: Decomposes a complex prompt into smaller sub-tasks.
    - `parallel_executor.py`: Runs sub-tasks concurrently via `asyncio.gather`.
- `/ui`
    - `server.py`: FastAPI backend (`/health`, `/status`, `/query`).
    - `app.py`: Streamlit dashboard.
- `/wrappers`
    - `base_wrapper.py`: Abstract base class for all wrappers.
    - `ollama_wrapper.py`: Local models via the Ollama HTTP API.
- `/tests`: Unit tests (no network or LLM required).
- `/data`: Persistent quota state (git-ignored).

## 🛠️ Installation

Requires **Python 3.12+** (3.14 tested). If it is missing:

```powershell
winget install --scope user Python.Python.3.14
```

Then create the virtual environment and install dependencies — one command:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

This creates `.venv`, installs `requirements.txt`, and runs the test suite.

<details>
<summary>Manual setup (equivalent)</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```
</details>

## ▶️ Running

One command starts both the backend and the dashboard:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Then open http://localhost:8501. Press Ctrl+C to stop both.

<details>
<summary>Running the two services manually</summary>

**Terminal 1 — backend**
```powershell
.\.venv\Scripts\python.exe -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — dashboard**
```powershell
.\.venv\Scripts\python.exe -m streamlit run ui/app.py
```
</details>

## 🔧 Configuration (environment variables)

| Variable | Default | Meaning |
| --- | --- | --- |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `llama3` | Model used by the Ollama wrapper |
| `OLLAMA_TIMEOUT` | `120` | Per-request timeout in seconds |

The Ollama wrapper needs the model to be installed locally:

```bash
ollama pull llama3
```

## 🧪 Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests run offline — no LLM or network access required.

## 📡 API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness probe |
| GET | `/status` | Registered models + quota snapshot |
| POST | `/query` | `{prompt, model: "auto"\|"Ollama", parallel: bool}` |

Example:

```bash
curl -X POST http://127.0.0.1:8000/query ^
  -H "Content-Type: application/json" ^
  -d "{\"prompt\": \"Say hi\", \"model\": \"auto\", \"parallel\": false}"
```

## 📈 Current Status

- [x] **Core Infrastructure:** modular wrapper system + dispatcher
- [x] **Intelligent Routing:** triage + capability/cost-based selection
- [x] **Quota Management:** persistent usage tracking + auto-fallback
- [x] **UI Prototype:** working dashboard + API bridge
- [x] **Parallelism:** task decomposition + async execution
- [ ] **Cloud/CLI wrappers:** Claude Code, Codex, Antigravity, **Hermes**

> CLI agent wrappers simply shell out to the tool and capture stdout — any agent
> with a non-interactive mode (e.g. `hermes -z "prompt"`) can be plugged in.
> Providers exposing an OpenAI-compatible endpoint (e.g. `hermes proxy`) can
> reuse a shared client wrapper.
- [ ] **Device benchmark / model recommendation**
- [ ] **Librarian** (model discovery & scoring) and **Tech Scout** (self-evolution)

## ⏭️ Next Steps

1. Add real wrappers for cloud providers and CLI agents.
2. Add device benchmarking to recommend the best local model.
3. Build the `Librarian` agent for automatic model discovery and scoring.
4. Implement the `Tech Scout` for self-evolution and auto-updating.
