from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core.dispatcher import Dispatcher
from wrappers.ollama_wrapper import OllamaWrapper
from wrappers.hermes_wrapper import HermesWrapper
from core.router import IntelligentRouter
from core.quota_manager import QuotaManager
from core.planner import TaskPlanner
from core.parallel_executor import ParallelExecutor

app = FastAPI(title="Nexus AI Studio API")
dispatcher = Dispatcher()
router = IntelligentRouter()
quota_manager = QuotaManager()
planner = TaskPlanner()
executor = ParallelExecutor(dispatcher, router)

# Register default wrappers
dispatcher.register_wrapper("Ollama", OllamaWrapper())

# Hermes is optional: only register it when the CLI is actually installed.
hermes = HermesWrapper()
if hermes.is_available():
    dispatcher.register_wrapper("Hermes", hermes)
else:
    print("[Startup] Hermes CLI bulunamadi; 'Hermes' kaydedilmedi.")


class QueryRequest(BaseModel):
    prompt: str
    model: str = "auto"
    parallel: bool = False


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "registered_models": list(dispatcher.wrappers.keys()),
        "quotas": quota_manager.get_quota_status(),
    }


@app.post("/query")
async def query_model(request: QueryRequest):
    try:
        # If parallel is requested, use the ParallelExecutor flow
        if request.parallel:
            sub_tasks = await planner.decompose(request.prompt)
            results = await executor.run_parallel(sub_tasks)

            # Charge each model that actually handled a sub-task.
            for result in results.values():
                quota_manager.consume_quota(result["model"])

            return {
                "type": "parallel",
                "sub_tasks_count": len(sub_tasks),
                "responses": results,
                "auto_routed": True,
            }

        # Standard Single-Model Flow
        model_to_use = request.model
        if model_to_use == "auto":
            model_to_use = await router.select_best_model(
                request.prompt, list(dispatcher.wrappers.keys())
            )

        if model_to_use not in dispatcher.wrappers:
            model_to_use = list(dispatcher.wrappers.keys())[0] if dispatcher.wrappers else "Ollama"

        quota_manager.consume_quota(model_to_use)
        result = await dispatcher.dispatch(model_to_use, request.prompt)
        return {
            "type": "single",
            "model": model_to_use,
            "response": result,
            "auto_routed": request.model == "auto",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
