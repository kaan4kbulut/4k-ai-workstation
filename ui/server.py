from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from core.dispatcher import Dispatcher
from wrappers.ollama_wrapper import OllamaWrapper
from core.router import IntelligentRouter
from core.quota_manager import QuotaManager
from core.planner import TaskPlanner
from core.parallel_executor import ParallelExecutor
from core.provider_config import (
    load_provider_configs,
    build_wrapper,
    upsert_provider_config,
    delete_provider_config,
)
from core.cli_registry import discover_cli_tools, register_available_cli_wrappers
from core.librarian import ModelLibrarian
from core.tech_scout import TechScout
from core.session_memory import SessionMemory
from core.workspace_builder import WorkspaceBuilder
from core.usage_tracker import UsageTracker

app = FastAPI(title="4K AI WORKSTATION API", version="2.0.0")
quota_manager = QuotaManager()
dispatcher = Dispatcher()
router = IntelligentRouter(quota_manager=quota_manager)
planner = TaskPlanner()
executor = ParallelExecutor(dispatcher, router)
librarian = ModelLibrarian()
tech_scout = TechScout()
session_memory = SessionMemory()
usage_tracker = UsageTracker()

# Varsayılan yerel çalışma zamanını kaydet
dispatcher.register_wrapper("Ollama", OllamaWrapper())

# Sistemde kurulu CLI ajanlarını (Hermes, Codex, Claude Code, OpenCode) otomatik kaydet
_registered_clis = register_available_cli_wrappers(dispatcher, router)
if _registered_clis:
    print(f"[Başlangıç] Kurulu CLI ajanları kaydedildi: {', '.join(_registered_clis)}")
else:
    print("[Başlangıç] Ek CLI ajanı bulunamadı.")


def _reload_configured_providers() -> list[str]:
    loaded: list[str] = []
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
            loaded.append(_cfg.name)
            print(f"[Başlangıç] Sağlayıcı kaydedildi: {_cfg.name} ({_cfg.model})")
    except Exception as _exc:
        print(f"[Başlangıç] Sağlayıcı yapılandırması yüklenemedi: {_exc}")
    return loaded


_reload_configured_providers()


class QueryRequest(BaseModel):
    prompt: str
    model: str = "auto"
    parallel: bool = False
    synthesize: bool = True
    use_llm_planner: bool = False
    session_id: str = "varsayilan"
    use_memory: bool = False
    workspace: str | None = None


class ProviderUpsertRequest(BaseModel):
    name: str
    base_url: str
    model: str
    api_key: str | None = None
    api_key_env: str | None = None
    capability: int = 8
    cost: float = 0.01
    local: bool = False
    strengths: list[str] = ["chat"]


class QuotaLimitRequest(BaseModel):
    model: str
    limit: int


class QuotaResetRequest(BaseModel):
    model: str | None = None


class ModelPullRequest(BaseModel):
    model: str


class LLMBenchmarkRequest(BaseModel):
    model: str = "llama3"


class WorkspaceBuildRequest(BaseModel):
    prompt: str
    workspace: str
    model: str = "auto"


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/status")
async def get_status():
    return {
        "status": "online",
        "registered_models": list(dispatcher.wrappers.keys()),
        "quotas": quota_manager.get_quota_status(),
        "sessions": session_memory.list_sessions(),
    }


@app.get("/cli/tools")
async def get_cli_tools():
    tools = [t.to_dict() for t in discover_cli_tools()]
    return {
        "status": "ok",
        "installed_count": sum(1 for t in tools if t["installed"]),
        "tools": tools,
    }


@app.get("/providers")
async def list_providers():
    configs = load_provider_configs()
    return {
        "status": "ok",
        "providers": [
            {
                "name": c.name,
                "base_url": c.base_url,
                "model": c.model,
                "has_api_key": bool(c.api_key),
                "capability": c.capability_score,
                "cost": c.cost_per_token,
                "local": c.is_local,
                "strengths": list(c.strengths),
            }
            for c in configs
        ],
    }


@app.post("/providers")
async def save_provider(req: ProviderUpsertRequest):
    entry = {
        "name": req.name.strip(),
        "base_url": req.base_url.strip(),
        "model": req.model.strip(),
        "capability": req.capability,
        "cost": req.cost,
        "local": req.local,
        "strengths": req.strengths,
    }
    if req.api_key:
        entry["api_key"] = req.api_key.strip()
    if req.api_key_env:
        entry["api_key_env"] = req.api_key_env.strip()

    upsert_provider_config(entry)
    loaded = _reload_configured_providers()
    return {"status": "ok", "registered_providers": loaded}


@app.delete("/providers/{name}")
async def remove_provider(name: str):
    delete_provider_config(name)
    if name in dispatcher.wrappers and name not in ("Ollama", "Hermes", "Codex", "Claude", "OpenCode"):
        del dispatcher.wrappers[name]
    return {"status": "ok", "registered_models": list(dispatcher.wrappers.keys())}


@app.post("/quotas/limit")
async def update_quota_limit(req: QuotaLimitRequest):
    quotas = quota_manager.set_quota_limit(req.model, req.limit)
    return {"status": "ok", "quotas": quotas}


@app.post("/quotas/reset")
async def reset_quotas(req: QuotaResetRequest):
    quotas = quota_manager.reset_quota(req.model)
    return {"status": "ok", "quotas": quotas}


@app.get("/sessions")
async def list_sessions():
    return {"status": "ok", "sessions": session_memory.list_sessions()}


@app.get("/sessions/{session_id}")
async def get_session_history(session_id: str):
    return {
        "status": "ok",
        "session_id": session_id,
        "history": session_memory.get_history(session_id),
    }


@app.delete("/sessions/{session_id}")
async def clear_session_history(session_id: str):
    session_memory.clear_session(session_id)
    return {"status": "ok", "session_id": session_id}


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


@app.post("/hardware/llm-benchmark")
async def run_llm_benchmark(req: LLMBenchmarkRequest):
    from core.benchmark import llm_benchmark

    return await llm_benchmark(model=req.model)


@app.post("/hardware/pull-model")
async def pull_model(req: ModelPullRequest):
    from core.benchmark import pull_ollama_model

    return await pull_ollama_model(model=req.model)


@app.get("/librarian/catalog")
async def librarian_catalog(
    task_type: str = "general",
    only_free: bool = False,
    include_online: bool = False,
):
    try:
        from core.hardware import get_system_info

        await librarian.refresh_catalog(include_online=include_online)
        hw = get_system_info()
        ranked = librarian.rank_models_for_task(
            task_type=task_type,
            max_vram_gb=hw.gpu_vram_gb,
            only_free_or_local=only_free,
        )
        return {
            "status": "ok",
            "task_type": task_type,
            "online_scanned": include_online,
            "models": ranked,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/scout/report")
async def scout_report(include_online: bool = False):
    try:
        from core.hardware import get_system_info

        installed_ollama = await librarian.fetch_installed_ollama_models()
        report = await tech_scout.full_scout_report(
            hw_info=get_system_info(),
            installed_ollama_models=installed_ollama,
            include_online=include_online,
        )
        return {"status": "ok", **report}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/usage/report")
async def get_usage_report(include_antigravity: bool = True):
    try:
        report = usage_tracker.get_report(include_antigravity=include_antigravity)
        report["markdown"] = usage_tracker.format_all_in_one_markdown(
            include_antigravity=include_antigravity
        )
        return report
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.post("/query")
async def query_model(request: QueryRequest):
    try:
        # Hızlı Kullanım / Tasarruf Raporu Komutu
        if request.prompt.strip().lower() in ("usage", "kullanım", "/usage"):
            return {
                "type": "single",
                "model": "UsageTracker",
                "response": usage_tracker.format_all_in_one_markdown(include_antigravity=True),
                "auto_routed": False,
                "escalated": False,
                "attempts": [],
                "session_id": request.session_id,
            }

        effective_prompt = (
            session_memory.build_contextual_prompt(request.session_id, request.prompt)
            if request.use_memory
            else request.prompt
        )

        # Paralel istendiyse ParallelExecutor + (isteğe bağlı) Sentezleyici akışını kullan
        if request.parallel:
            if request.use_llm_planner:
                sub_tasks = await planner.decompose_with_llm(effective_prompt, dispatcher)
            else:
                sub_tasks = await planner.decompose(effective_prompt)

            results = await executor.run_parallel(sub_tasks)

            for result in results.values():
                m_name = result["model"]
                quota_manager.consume_quota(m_name)
                m_info = usage_tracker.classify_model_or_tool(m_name)
                usage_tracker.record_event(
                    category="model",
                    name=m_name,
                    tier=m_info["tier"],
                    is_free=m_info["is_free"],
                    source="workstation",
                )

            synthesis = None
            if request.synthesize and len(sub_tasks) > 1:
                synthesis = await executor.synthesize_results(
                    request.prompt, sub_tasks, results
                )
                if synthesis:
                    s_name = synthesis["model"]
                    quota_manager.consume_quota(s_name)
                    s_info = usage_tracker.classify_model_or_tool(s_name)
                    usage_tracker.record_event(
                        category="model",
                        name=s_name,
                        tier=s_info["tier"],
                        is_free=s_info["is_free"],
                        source="workstation",
                    )

            final_text = (
                synthesis["response"]
                if synthesis
                else "\n\n".join(r["response"] for r in results.values())
            )
            if request.use_memory:
                session_memory.append_turn(
                    request.session_id,
                    request.prompt,
                    final_text,
                    synthesis["model"] if synthesis else "Parallel",
                )

            return {
                "type": "parallel",
                "sub_tasks_count": len(sub_tasks),
                "responses": results,
                "synthesis": synthesis,
                "auto_routed": True,
            }

        # Standart tek-model akışı (Otomatik Eskalasyon destekli)
        available = list(dispatcher.wrappers.keys())
        if request.model == "auto":
            chain = await router.rank_escalation_chain(effective_prompt, available)
        else:
            fallback_chain = await router.rank_escalation_chain(effective_prompt, available)
            first = request.model if request.model in dispatcher.wrappers else (available[0] if available else "Ollama")
            chain = [first] + [m for m in fallback_chain if m != first]

        esc_result = await dispatcher.dispatch_with_escalation(
            chain, effective_prompt, workspace=request.workspace
        )
        model_used = esc_result["model"]
        result_text = esc_result["response"]

        quota_manager.consume_quota(model_used)
        m_info = usage_tracker.classify_model_or_tool(model_used)
        usage_tracker.record_event(
            category="model",
            name=model_used,
            tier=m_info["tier"],
            is_free=m_info["is_free"],
            source="workstation",
        )
        if request.use_memory:
            session_memory.append_turn(
                request.session_id, request.prompt, result_text, model_used
            )

        return {
            "type": "single",
            "model": model_used,
            "response": result_text,
            "auto_routed": request.model == "auto",
            "escalated": esc_result["escalated"],
            "attempts": esc_result["attempts"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/workspace/build")
async def build_workspace(req: WorkspaceBuildRequest):
    try:
        project_prompt = WorkspaceBuilder.build_project_prompt(req.prompt)
        available = list(dispatcher.wrappers.keys())
        if req.model == "auto":
            chain = await router.rank_escalation_chain(project_prompt, available)
        else:
            fallback_chain = await router.rank_escalation_chain(project_prompt, available)
            first = (
                req.model
                if req.model in dispatcher.wrappers
                else (available[0] if available else "Ollama")
            )
            chain = [first] + [m for m in fallback_chain if m != first]

        esc_result = await dispatcher.dispatch_with_escalation(
            chain, project_prompt, workspace=req.workspace
        )
        model_used = esc_result["model"]
        response_text = esc_result["response"]

        quota_manager.consume_quota(model_used)
        m_info = usage_tracker.classify_model_or_tool(model_used)
        usage_tracker.record_event(
            category="model",
            name=model_used,
            tier=m_info["tier"],
            is_free=m_info["is_free"],
            source="workstation",
        )

        extracted = WorkspaceBuilder.extract_files_from_response(response_text)
        created_files = WorkspaceBuilder.apply_files(req.workspace, extracted)

        return {
            "status": "ok",
            "model": model_used,
            "created_files": created_files,
            "files_count": len(created_files),
            "response": response_text,
            "escalated": esc_result.get("escalated", False),
            "attempts": esc_result.get("attempts", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
