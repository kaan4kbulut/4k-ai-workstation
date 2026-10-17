from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core.dispatcher import Dispatcher
from wrappers.ollama_wrapper import OllamaWrapper
from wrappers.hermes_wrapper import HermesWrapper
from core.router import IntelligentRouter
from core.quota_manager import QuotaManager
from core.planner import TaskPlanner
from core.parallel_executor import ParallelExecutor
from core.provider_config import load_provider_configs, build_wrapper

app = FastAPI(title="Nexus AI Studio API")
dispatcher = Dispatcher()
router = IntelligentRouter()
quota_manager = QuotaManager()
planner = TaskPlanner()
executor = ParallelExecutor(dispatcher, router)

# Varsayılan wrapper'ları kaydet
dispatcher.register_wrapper("Ollama", OllamaWrapper())

# Hermes isteğe bağlıdır: yalnızca CLI gerçekten kuruluysa kaydedilir.
hermes = HermesWrapper()
if hermes.is_available():
    dispatcher.register_wrapper("Hermes", hermes)
else:
    print("[Başlangıç] Hermes CLI bulunamadı; 'Hermes' kaydedilmedi.")

# OpenAI uyumlu sağlayıcıları yapılandırmadan yükle (config/providers.json).
# Böylece OpenRouter, HuggingFace, Perplexity, OpenAI vb. kod yazmadan eklenir.
try:
    for _cfg in load_provider_configs():
        dispatcher.register_wrapper(_cfg.name, build_wrapper(_cfg))
        router.register_tier(
            _cfg.name,
            capability_score=_cfg.capability_score,
            cost_per_token=_cfg.cost_per_token,
            is_local=_cfg.is_local,
            strengths=_cfg.strengths,
        )
        print(f"[Başlangıç] Sağlayıcı kaydedildi: {_cfg.name} ({_cfg.model})")
except Exception as _exc:  # yapılandırma hatası sunucuyu düşürmesin
    print(f"[Başlangıç] Sağlayıcı yapılandırması yüklenemedi: {_exc}")


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


@app.get("/hardware/info")
async def hardware_info():
    try:
        from core.hardware import get_system_info

        info = get_system_info()
        return {
            "status": "ok",
            "info": {
                "os_name": info.os_name,
                "cpu_cores": info.cpu_cores,
                "ram_gb": info.ram_gb,
                "gpu_name": info.gpu_name,
                "gpu_vram_gb": info.gpu_vram_gb,
            },
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/hardware/recommend")
async def hardware_recommend():
    try:
        from core.hardware import get_system_info, recommend_local_models

        info = get_system_info()
        recs = recommend_local_models(info)
        return {
            "status": "ok",
            "info": {
                "cpu_cores": info.cpu_cores,
                "ram_gb": info.ram_gb,
                "gpu_vram_gb": info.gpu_vram_gb,
            },
            "recommendations": [
                {"model": r.model, "reason": r.reason, "fit": r.fit} for r in recs
            ],
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/query")
async def query_model(request: QueryRequest):
    try:
        # Paralel istendiyse ParallelExecutor akışını kullan
        if request.parallel:
            sub_tasks = await planner.decompose(request.prompt)
            results = await executor.run_parallel(sub_tasks)

            # Gerçekten her alt görevi işleyen modelden kota düş.
            for result in results.values():
                quota_manager.consume_quota(result["model"])

            return {
                "type": "parallel",
                "sub_tasks_count": len(sub_tasks),
                "responses": results,
                "auto_routed": True,
            }

        # Standart tek-model akışı
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
