from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core.dispatcher import Dispatcher
from wrappers.ollama_wrapper import OllamaWrapper
from core.router import IntelligentRouter
from core.quota_manager import QuotaManager
from core.planner import TaskPlanner
from core.parallel_executor import ParallelExecutor
from core.provider_config import load_provider_configs, build_wrapper
from core.cli_registry import discover_cli_tools, register_available_cli_wrappers
from core.librarian import ModelLibrarian
from core.tech_scout import TechScout

app = FastAPI(title="Nexus AI Studio API")
dispatcher = Dispatcher()
router = IntelligentRouter()
quota_manager = QuotaManager()
planner = TaskPlanner()
executor = ParallelExecutor(dispatcher, router)
librarian = ModelLibrarian()
tech_scout = TechScout()

# Varsayılan yerel çalışma zamanını kaydet
dispatcher.register_wrapper("Ollama", OllamaWrapper())

# Sistemde kurulu CLI ajanlarını (Hermes, Codex, Claude Code, OpenCode) otomatik kaydet
_registered_clis = register_available_cli_wrappers(dispatcher, router)
if _registered_clis:
    print(f"[Başlangıç] Kurulu CLI ajanları kaydedildi: {', '.join(_registered_clis)}")
else:
    print("[Başlangıç] Ek CLI ajanı bulunamadı.")

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


@app.get("/cli/tools")
async def get_cli_tools():
    tools = [t.to_dict() for t in discover_cli_tools()]
    return {
        "status": "ok",
        "installed_count": sum(1 for t in tools if t["installed"]),
        "tools": tools,
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
                "gpu_name": info.gpu_name,
                "gpu_vram_gb": info.gpu_vram_gb,
            },
            "recommendations": [
                {"model": r.model, "reason": r.reason, "fit": r.fit} for r in recs
            ],
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/hardware/benchmark")
async def hardware_benchmark():
    try:
        from core.benchmark import benchmark

        return {"status": "ok", "benchmark": benchmark()}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/librarian/catalog")
async def librarian_catalog(task_type: str = "general", only_free: bool = False):
    try:
        from core.hardware import get_system_info

        await librarian.refresh_catalog()
        hw = get_system_info()
        ranked = librarian.rank_models_for_task(
            task_type=task_type,
            max_vram_gb=hw.gpu_vram_gb,
            only_free_or_local=only_free,
        )
        return {
            "status": "ok",
            "task_type": task_type,
            "models": ranked,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/scout/report")
async def scout_report():
    try:
        from core.hardware import get_system_info

        installed_ollama = await librarian.fetch_installed_ollama_models()
        report = tech_scout.analyze_system(
            hw_info=get_system_info(),
            installed_ollama_models=installed_ollama,
        )
        return {"status": "ok", **report}
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
