from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from typing import List, Dict, Any
from core.dispatcher import Dispatcher
from wrappers.ollama_wrapper import OllamaWrapper
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

class QueryRequest(BaseModel):
    prompt: str
    model: str = "auto"
    parallel: bool = False

@app.get("/status")
async def get_status():
    return {
        "status": "online", 
        "registered_models": list(dispatcher.wrappers.keys()),
        "quotas": quota_manager.get_quota_status()
    }

@app.post("/query")
async def query_model(request: QueryRequest):
    try:
        # If parallel is requested, use the ParallelExecutor flow
        if request.parallel:
            sub_tasks = await planner.decompose(request.prompt)
            results = await executor.run_parallel(sub_tasks)
            
            # Consume quotas for all models used in parallel
            # Note: In a real version, executor would return which models were used
            # For now, we simulate it by using a dummy consumption or tracking via executor
            for task_id, response in results.items():
                # We can't easily track which model was used per task here without modifying executor
                # For the prototype, we assume the router's selection logic ran
                # We'll add a simpler quota consume for the main prompt
                quota_manager.consume_quota("Ollama") # Default for prototype
            
            return {
                "type": "parallel",
                "sub_tasks_count": len(sub_tasks),
                "responses": results,
                "auto_routed": True
            }

        # Standard Single-Model Flow
        model_to_use = request.model
        if model_to_use == "auto":
            model_to_use = await router.select_best_model(request.prompt)
        
        if model_to_use not in dispatcher.wrappers:
            model_to_use = list(dispatcher.wrappers.keys())[0] if dispatcher.wrappers else "Ollama"
            
        quota_manager.consume_quota(model_to_use)
        result = await dispatcher.dispatch(model_to_use, request.prompt)
        return {"type": "single", "model": model_to_use, "response": result, "auto_routed": True if request.model == "auto" else False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)