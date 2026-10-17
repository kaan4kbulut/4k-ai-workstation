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

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## ▶️ Running

Two terminals, from the project root:

**Terminal 1 — backend**
```bash
python -m uvicorn ui.server:app --host 127.0.0.1 --port 8000
```

**Terminal 2 — dashboard**
```bash
python -m streamlit run ui/app.py
```

Then open http://localhost:8501.

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

```bash
python -m unittest discover -s tests -v
```

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
- [ ] **Cloud/CLI wrappers:** Claude Code, Codex, Antigravity
- [ ] **Device benchmark / model recommendation**
- [ ] **Librarian** (model discovery & scoring) and **Tech Scout** (self-evolution)

## ⏭️ Next Steps

1. Add real wrappers for cloud providers and CLI agents.
2. Add device benchmarking to recommend the best local model.
3. Build the `Librarian` agent for automatic model discovery and scoring.
4. Implement the `Tech Scout` for self-evolution and auto-updating.
