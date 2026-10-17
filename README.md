# 🚀 Nexus AI Studio

An Intelligent AI Orchestrator and Model Gateway. This system manages multiple LLM providers (Cloud & Local), routes tasks based on complexity, tracks quotas, and executes sub-tasks in parallel.

## 📁 Project Structure
- `/core`: The brain of the system.
    - `dispatcher.py`: Manages communication with model wrappers.
    - `router.py`: Determines the best model based on task complexity.
    - `quota_manager.py`: Tracks usage limits for each model.
    - `planner.py`: Decomposes complex prompts into smaller sub-tasks.
    - `parallel_executor.py`: Runs multiple model requests concurrently.
- `/ui`: User Interface layer.
    - `server.py`: FastAPI backend that bridges the UI and the Core.
    - `app.py`: Streamlit dashboard for user interaction.
- `/wrappers`: Integration layer for different AI tools.
    - `base_wrapper.py`: Abstract base class for all wrappers.
    - `ollama_wrapper.py`: Implementation for local models via Ollama.
- `/data`: Persistent storage for quotas and settings.

## 🛠️ Installation & Setup

### 1. Dependencies
Install the required Python libraries:
```bash
pip install fastapi uvicorn streamlit requests
```

### 2. Running the System
You need two terminal windows:

**Terminal 1: Start the Backend Server**
```bash
python nexus_ai_studio/ui/server.py
```

**Terminal 2: Start the Frontend Dashboard**
```bash
streamlit run nexus_ai_studio/ui/app.py
```

## 📈 Current Status (Checkpoint)
- [x] **Core Infrastructure:** Modular wrapper system and dispatcher are functional.
- [x] **Intelligent Routing:** Basic triaging and capability-based model selection implemented.
- [x] **Quota Management:** Usage tracking and auto-fallback logic implemented.
- [x] **UI Prototype:** Functional Dashboard with Parallel Execution toggle.
- [x] **Parallelism:** Task decomposition and async execution engine fully integrated into UI.

## ⏭️ Next Steps for Resumption
1. Implement additional wrappers (Claude Code, Codex, etc.) for multi-model testing.
2. Build the `Librarian` agent for automatic model discovery and scoring (Phase 4).
3. Implement the `Tech Scout` for self-evolution and auto-updating (Phase 5).