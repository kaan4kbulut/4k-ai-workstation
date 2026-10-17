"""Nexus AI Studio - Kapsamlı Streamlit Kontrol Paneli (Web UI).

Bu modül Nexus AI Studio ekosisteminin tüm yeteneklerini tek bir merkezden yöneten
5 sekmeli, modern ve Türkçe arayüzü sunar:
  1. ⚡ Komut Merkezi (Oturum hafızası, eskalasyon takibi, paralel yürütme & sentezleyici)
  2. 🛠️ CLI Ajanları, Sağlayıcılar & Kotalar (Abonelikler, Bulut API şablonları & Kota yönetimi)
  3. 🏎️ Donanım, Benchmark & Model İndir (Donanım önerileri, tek tıkla indirme & gerçek LLM hız testi)
  4. 📚 Model Kütüphanecisi (Librarian) (Yetenek matrisi & canlı OpenRouter/HuggingFace taraması)
  5. 🔭 Teknoloji Gözcüsü (Tech Scout) (Sistem analiz bulguları, paketler & canlı GitHub AI trendleri)
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Sayfa Yapılandırması ve Temel Ayarlar
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Nexus AI Studio",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Özel CSS Stillendirmesi
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 12px 16px;
        border-left: 4px solid #1E88E5;
        margin-bottom: 10px;
    }
    .badge-success {
        background-color: #E8F5E9;
        color: #2E7D32;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-warning {
        background-color: #FFF3E0;
        color: #E65100;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-danger {
        background-color: #FFEBEE;
        color: #C62828;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .badge-info {
        background-color: #E3F2FD;
        color: #1565C0;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding-top: 8px;
        padding-bottom: 8px;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# API İstemci Yardımcıları
# ---------------------------------------------------------------------------
if "api_base" not in st.session_state:
    st.session_state["api_base"] = "http://localhost:8000"

API_BASE = st.session_state["api_base"].rstrip("/")


def api_get(endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """API sunucusuna GET isteği atar, hata durumunda kullanıcıyı uyarır."""
    try:
        res = requests.get(f"{API_BASE}{endpoint}", params=params, timeout=timeout)
        if res.status_code == 200:
            return res.json()
        st.error(f"Sunucu Hatası [{res.status_code}]: {res.text[:200]}")
    except requests.exceptions.ConnectionError:
        st.error(f"API Sunucusuna bağlanılamadı ({API_BASE}). Lütfen sunucunun çalıştığından emin olun.")
    except Exception as exc:
        st.error(f"İstek Hatası: {exc}")
    return None


def api_post(endpoint: str, json_data: Optional[Dict[str, Any]] = None, timeout: int = 300) -> Optional[Dict[str, Any]]:
    """API sunucusuna POST isteği atar."""
    try:
        res = requests.post(f"{API_BASE}{endpoint}", json=json_data or {}, timeout=timeout)
        if res.status_code == 200:
            return res.json()
        st.error(f"Sunucu Hatası [{res.status_code}]: {res.text[:200]}")
    except requests.exceptions.ConnectionError:
        st.error(f"API Sunucusuna bağlanılamadı ({API_BASE}).")
    except Exception as exc:
        st.error(f"İstek Hatası: {exc}")
    return None


def api_delete(endpoint: str, timeout: int = 15) -> Optional[Dict[str, Any]]:
    """API sunucusuna DELETE isteği atar."""
    try:
        res = requests.delete(f"{API_BASE}{endpoint}", timeout=timeout)
        if res.status_code == 200:
            return res.json()
        st.error(f"Sunucu Hatası [{res.status_code}]: {res.text[:200]}")
    except requests.exceptions.ConnectionError:
        st.error(f"API Sunucusuna bağlanılamadı ({API_BASE}).")
    except Exception as exc:
        st.error(f"İstek Hatası: {exc}")
    return None


# ---------------------------------------------------------------------------
# Kenar Çubuğu (Sidebar) - Sistem Durumu & Donanım Özeti
# ---------------------------------------------------------------------------
st.sidebar.title("🚀 Nexus AI Studio")
st.sidebar.caption("Akıllı Çoklu Ajan ve LLM Orkestrasyonu")

with st.sidebar.expander("⚙️ Bağlantı Ayarları", expanded=False):
    new_api = st.text_input("API Sunucu Adresi:", value=st.session_state["api_base"])
    if new_api != st.session_state["api_base"]:
        st.session_state["api_base"] = new_api
        st.rerun()

# Sunucu Durumunu Al
status_data = api_get("/status", timeout=4)
registered_models: List[str] = []
current_quotas: Dict[str, Any] = {}
available_sessions: List[str] = ["varsayilan"]

if status_data and status_data.get("status") == "online":
    st.sidebar.success("🟢 API Sunucusu Çevrimiçi")
    registered_models = status_data.get("registered_models", [])
    current_quotas = status_data.get("quotas", {})
    available_sessions = status_data.get("sessions", ["varsayilan"]) or ["varsayilan"]
else:
    st.sidebar.error("🔴 API Sunucusu Çevrimdışı")
    st.sidebar.info("Lütfen arka planda `python ui/server.py` çalıştırın.")

st.sidebar.subheader("Aktif Model & Ajanlar")
if registered_models:
    for m in registered_models:
        st.sidebar.markdown(f"- `{m}`")
else:
    st.sidebar.caption("Kayıtlı model bulunamadı.")

# Sidebar Donanım Özeti
with st.sidebar.expander("💻 Donanım Özeti", expanded=True):
    hw_info_data = api_get("/hardware/info", timeout=4)
    if hw_info_data and hw_info_data.get("status") == "ok":
        info = hw_info_data.get("info", {})
        st.write(f"**İşletim Sistemi:** {info.get('os_name')}")
        st.write(f"**CPU:** {info.get('cpu_cores')} Çekirdek")
        st.write(f"**RAM:** {info.get('ram_gb')} GB")
        st.write(f"**GPU:** {info.get('gpu_name') or 'Algılanamadı'}")
        st.write(f"**VRAM:** {info.get('gpu_vram_gb', 0)} GB")
    else:
        st.caption("Donanım bilgisi alınamadı.")

st.sidebar.divider()
st.sidebar.caption("Nexus AI Studio v2.0 | Yerel & Bulut Hibrit")

# ---------------------------------------------------------------------------
# Ana Başlık ve 5 Sekmeli Arayüz
# ---------------------------------------------------------------------------
st.title("🎯 Nexus AI Studio Kontrol Paneli")

tab_cmd, tab_cli, tab_hw, tab_lib, tab_scout = st.tabs(
    [
        "⚡ Komut Merkezi",
        "🛠️ CLI Ajanları, Sağlayıcılar & Kotalar",
        "🏎️ Donanım, Benchmark & Model İndir",
        "📚 Model Kütüphanecisi (Librarian)",
        "🔭 Teknoloji Gözcüsü (Tech Scout)",
    ]
)

# ===========================================================================
# SEKME 1: ⚡ Komut Merkezi
# ===========================================================================
with tab_cmd:
    st.subheader("⚡ Akıllı Yönlendirme ve Görev Dağıtım Merkezi")
    st.write(
        "Doğal dildeki isteklerinizi analiz ederek en uygun yerel modele, CLI ajanına veya bulut sağlayıcıya "
        "otomatik yönlendirir; gerektiğinde karmaşık görevleri paralel alt görevlere bölüp sentezler."
    )

    # Yapılandırma Kutusu
    with st.container():
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.markdown("##### 📁 Oturum & Çok Turlu Hafıza")
            sess_mode = st.radio(
                "Oturum Seçimi:",
                ["Mevcut Oturum", "Yeni Oturum Oluştur"],
                horizontal=True,
                key="sess_mode_radio",
            )
            if sess_mode == "Mevcut Oturum" and available_sessions:
                active_session_id = st.selectbox(
                    "Aktif Oturum:", available_sessions, index=0, key="select_existing_sess"
                )
            else:
                active_session_id = st.text_input(
                    "Yeni Oturum Adı / ID:", value="proje_sohbeti", key="new_sess_input"
                ).strip() or "varsayilan"

            use_memory = st.checkbox(
                "🧠 Çok Turlu Sohbet Hafızasını Kullan (use_memory)",
                value=True,
                help="Önceki istekleri ve model yanıtlarını yeni isteklerin başına bağlam olarak otomatik ekler.",
            )

            workspace = st.text_input(
                "Hedef Proje Dizini (Workspace - İsteğe Bağlı):",
                placeholder="Örn: C:\\Users\\kloss\\nexus_ai_studio",
                help="CLI kodlama ajanlarının (Claude Code, Hermes vb.) çalışacağı hedef çalışma dizini.",
            )

        with col_c2:
            st.markdown("##### ⚙️ Model Seçimi & Paralel Dağıtım")
            model_options = ["auto"] + [m for m in registered_models if m != "auto"]
            selected_model = st.selectbox(
                "Model / Ajan Seçimi:",
                model_options,
                index=0,
                help="'auto' seçilirse Akıllı Yönlendirici (Router) isteği analiz edip en uygun modele yönlendirir.",
            )

            is_parallel = st.checkbox(
                "🔀 Paralel Çalıştırma (Görevi Böl ve Dağıt)",
                value=False,
                help="Görevi alt parçalara ayırarak uygun modellere/ajanlara aynı anda paralel gönderir.",
            )

            if is_parallel:
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    synthesize = st.checkbox(
                        "🧬 Çıktıları Tek Yanıtta Sentezle (Aggregator)",
                        value=True,
                        help="Tüm alt görevlerin çıktılarını birleştirici üst modele verip tek bir nihai rapor oluşturur.",
                    )
                with col_p2:
                    use_llm_planner = st.checkbox(
                        "🧠 LLM ile Görev Böl (use_llm_planner)",
                        value=False,
                        help="Görev ayrıştırmasını kural tabanlı değil, doğrudan zeki bir LLM ile yapar.",
                    )
            else:
                synthesize = True
                use_llm_planner = False

    # Oturum Geçmişi ve Temizleme
    with st.expander(f"📜 Aktif Oturum Geçmişi: '{active_session_id}'", expanded=False):
        sess_history_data = api_get(f"/sessions/{active_session_id}", timeout=5)
        turns = sess_history_data.get("history", []) if sess_history_data else []
        if turns:
            st.write(f"Toplam Konuşma Turu: **{len(turns)}**")
            for idx, turn in enumerate(turns, 1):
                st.markdown(f"**👤 Kullanıcı ({idx}):**")
                st.info(turn.get("user", ""))
                st.markdown(f"**🤖 Asistan ({turn.get('model', 'AI')}):**")
                st.markdown(turn.get("assistant", ""))
                st.divider()
        else:
            st.caption("Bu oturumda henüz kayıtlı bir konuşma turu bulunmuyor.")

        col_cl1, col_cl2 = st.columns([1, 4])
        with col_cl1:
            if st.button("🗑️ Oturumu Temizle", key="btn_clear_sess"):
                del_res = api_delete(f"/sessions/{active_session_id}")
                if del_res and del_res.get("status") == "ok":
                    st.success(f"'{active_session_id}' oturum geçmişi temizlendi!")
                    st.rerun()

    # İstek Giriş Alanı
    st.markdown("##### 📝 İstek / Görev Tanımı")
    user_prompt = st.text_area(
        "Nexus AI Studio'ya bir komut veya soru yazın:",
        placeholder="Örnek: Bu Python projesindeki mimariyi analiz et, birim testleri oluştur ve kod kalitesini artır...",
        height=130,
    )

    if st.button("🚀 Çalıştır (Dispatch)", type="primary", use_container_width=True):
        if not user_prompt.strip():
            st.warning("Lütfen çalıştırmak için bir istek veya komut girin.")
        else:
            with st.spinner("İstek analiz ediliyor ve yürütülüyor... Lütfen bekleyin."):
                payload = {
                    "prompt": user_prompt.strip(),
                    "model": selected_model,
                    "parallel": is_parallel,
                    "synthesize": synthesize,
                    "use_llm_planner": use_llm_planner,
                    "session_id": active_session_id,
                    "use_memory": use_memory,
                    "workspace": workspace.strip() if workspace.strip() else None,
                }
                res = api_post("/query", json_data=payload, timeout=300)

                if res:
                    st.session_state["last_query_result"] = res

    # Sonuçların Gösterimi
    if "last_query_result" in st.session_state:
        res = st.session_state["last_query_result"]
        res_type = res.get("type")

        st.markdown("---")
        st.markdown("### 📋 Yürütme Sonuçları")

        if res_type == "single":
            model_used = res.get("model")
            is_escalated = res.get("escalated", False)
            attempts = res.get("attempts", [])

            if is_escalated:
                st.warning("⚠️ **Otomatik Eskalasyon Devreye Girdi!**")
                steps_desc = []
                for att in attempts:
                    succ = att.get("success", False)
                    badge = "✅ Başarılı" if succ else f"❌ Başarısız ({att.get('error', 'Hata')})"
                    steps_desc.append(f"`{att.get('model')}` -> {badge}")
                st.markdown(
                    f"İlk model görevi tamamlayamadığı için istek daha yetenekli üst modele yükseltildi:\n\n"
                    + " ➔ ".join(steps_desc)
                )

            st.success(
                f"✅ Yanıt Üretildi | Kullanılan Model: **{model_used}** "
                + ("(Otomatik Yönlendirildi)" if res.get("auto_routed") else "")
            )

            st.markdown("#### 💬 Yanıt Metni")
            st.markdown(res.get("response", ""))

            if attempts and len(attempts) > 1:
                with st.expander("🔍 Eskalasyon Deneme Kayıtları", expanded=False):
                    st.json(attempts)

        elif res_type == "parallel":
            sub_count = res.get("sub_tasks_count", 0)
            st.info(f"⚡ Görev **{sub_count}** alt göreve ayrıldı ve paralel olarak çalıştırıldı.")

            synthesis = res.get("synthesis")
            if synthesis:
                st.markdown("### 🧬 Birleştirilmiş Nihai Yanıt (Sentezleyici / Aggregator)")
                st.caption(f"Sentezleyen Model: **{synthesis.get('model', 'Aggregator')}**")
                st.markdown(synthesis.get("response", ""))
                st.markdown("---")

            st.markdown("#### 🧩 Alt Görev Detayları")
            sub_responses = res.get("responses", {})
            for task_id, sub_res in sub_responses.items():
                with st.expander(f"📌 Alt Görev {task_id} — Model: {sub_res.get('model')}", expanded=False):
                    st.markdown(sub_res.get("response", ""))


# ===========================================================================
# SEKME 2: 🛠️ CLI Ajanları, Sağlayıcılar & Kotalar
# ===========================================================================
with tab_cli:
    st.subheader("🛠️ CLI Ajanları, Bulut Sağlayıcılar & Kota Yönetimi")

    tab_c_tools, tab_c_prov, tab_c_quota = st.tabs(
        ["🤖 Kurulu CLI Araçları", "🌐 Bulut Sağlayıcılar (API)", "📊 Kota ve Sayaç Yönetimi"]
    )

    # 1. Alt Sekme: CLI Araçları
    with tab_c_tools:
        st.markdown("##### 🖥️ Sistemde Kurulu Otonom CLI Ajanları")
        st.write(
            "Nexus AI Studio; sisteminizde kurulu Hermes, Claude Code, OpenCode ve Codex CLI "
            "araçlarını otomatik algılayarak hiçbir API anahtarı gerekmeden doğrudan abonelik kotanızla çalıştırır."
        )

        cli_tools_res = api_get("/cli/tools", timeout=6)
        if cli_tools_res and cli_tools_res.get("status") == "ok":
            installed_cnt = cli_tools_res.get("installed_count", 0)
            tools_list = cli_tools_res.get("tools", [])

            c_metric1, c_metric2 = st.columns(2)
            c_metric1.metric("Toplam Tanımlı CLI", len(tools_list))
            c_metric2.metric("Kurulu ve Kullanıma Hazır", installed_cnt)

            st.write("")
            for tool in tools_list:
                is_inst = tool.get("installed", False)
                status_badge = "✅ KURULU" if is_inst else "⚪ KURULU DEĞİL"
                header_title = f"{status_badge} — **{tool.get('name')}** ({tool.get('subscription_type')})"

                with st.expander(header_title, expanded=is_inst):
                    st.write(f"**Rol / İşlev:** {tool.get('role')}")
                    st.write(f"**Güçlü Olduğu Alanlar:** `{', '.join(tool.get('strengths', []))}`")
                    if is_inst:
                        st.write("**Çalıştırılabilir Dosya Yolu:**")
                        st.code(tool.get("binary_path"), language="text")
                    else:
                        st.warning(f"Bu araç kurulu değil. Kurmak için şu komutu kullanabilirsiniz:")
                        st.code(tool.get("install_hint"), language="bash")
        else:
            st.error("CLI araçları listesi alınamadı.")

    # 2. Alt Sekme: Bulut Sağlayıcılar
    with tab_c_prov:
        st.markdown("##### 🌐 Bulut LLM Sağlayıcıları ve Özel API Yapılandırması")
        st.write(
            "OpenAI uyumlu herhangi bir bulut API uç noktasını (OpenRouter, Groq, Perplexity vb.) "
            "Nexus yönlendiricisine ekleyin veya kaldırın."
        )

        # Mevcut Sağlayıcıları Listele
        prov_res = api_get("/providers", timeout=5)
        existing_provs = prov_res.get("providers", []) if prov_res else []

        st.markdown("###### Mevcut Kayıtlı Sağlayıcılar")
        if existing_provs:
            for p in existing_provs:
                p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns([2, 3, 2, 2, 1])
                with p_col1:
                    st.markdown(f"**{p.get('name')}**")
                    st.caption(f"Model: `{p.get('model')}`")
                with p_col2:
                    st.write(f"URL: `{p.get('base_url')}`")
                with p_col3:
                    key_badge = "🔑 API Key Var" if p.get("has_api_key") else "⚪ Ortam Değişkeni / Yok"
                    st.write(f"{key_badge} | Skor: `{p.get('capability')}/10`")
                with p_col4:
                    st.write(f"Maliyet: `${p.get('cost')}` | Güç: `{','.join(p.get('strengths', []))}`")
                with p_col5:
                    if st.button("🗑️ Sil", key=f"del_prov_{p.get('name')}"):
                        d_res = api_delete(f"/providers/{p.get('name')}")
                        if d_res and d_res.get("status") == "ok":
                            st.success(f"{p.get('name')} kaldırıldı!")
                            st.rerun()
                st.divider()
        else:
            st.info("Henüz harici bir bulut sağlayıcı yapılandırılmamış.")

        # Yeni Sağlayıcı Ekleme Formu
        st.markdown("###### ➕ Yeni Sağlayıcı Ekle / Güncelle")

        # Hızlı Şablonlar Sözlüğü
        TEMPLATES = {
            "Özel / Manuel Giriş": {
                "name": "",
                "base_url": "",
                "model": "",
                "api_key_env": "",
                "capability": 8,
                "cost": 0.01,
                "local": False,
                "strengths": ["chat"],
            },
            "OpenRouter (GPT-4o Mini)": {
                "name": "OpenRouter-Mini",
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-4o-mini",
                "api_key_env": "OPENROUTER_API_KEY",
                "capability": 9,
                "cost": 0.01,
                "local": False,
                "strengths": ["chat", "reasoning"],
            },
            "Perplexity (Sonar Reasoning)": {
                "name": "Perplexity-Sonar",
                "base_url": "https://api.perplexity.ai",
                "model": "sonar-reasoning",
                "api_key_env": "PERPLEXITY_API_KEY",
                "capability": 9,
                "cost": 0.01,
                "local": False,
                "strengths": ["reasoning", "chat"],
            },
            "HuggingFace Router (Qwen 2.5 Coder)": {
                "name": "HF-QwenCoder",
                "base_url": "https://api-inference.huggingface.co/v1",
                "model": "Qwen/Qwen2.5-Coder-32B-Instruct",
                "api_key_env": "HF_TOKEN",
                "capability": 9,
                "cost": 0.0,
                "local": False,
                "strengths": ["coding", "chat"],
            },
            "Groq (Llama 3.3 70B Versatile)": {
                "name": "Groq-Llama3.3",
                "base_url": "https://api.groq.com/openai/v1",
                "model": "llama-3.3-70b-versatile",
                "api_key_env": "GROQ_API_KEY",
                "capability": 9,
                "cost": 0.01,
                "local": False,
                "strengths": ["fast", "chat", "coding"],
            },
            "OpenAI (GPT-4o)": {
                "name": "OpenAI-GPT4o",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o",
                "api_key_env": "OPENAI_API_KEY",
                "capability": 10,
                "cost": 0.03,
                "local": False,
                "strengths": ["coding", "reasoning", "chat"],
            },
        }

        tpl_choice = st.selectbox("⚡ Hızlı Şablon Seçici:", list(TEMPLATES.keys()))
        t_data = TEMPLATES[tpl_choice]

        with st.form("add_provider_form"):
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                p_name = st.text_input("Sağlayıcı Adı (Benzersiz):", value=t_data["name"])
                p_url = st.text_input("Base URL (API Uç Noktası):", value=t_data["base_url"])
                p_model = st.text_input("Model Adı / Kodu:", value=t_data["model"])
                p_key = st.text_input("API Anahtarı (İsteğe Bağlı):", type="password")
            with col_f2:
                p_env = st.text_input("Ortam Değişkeni Adı (api_key_env):", value=t_data["api_key_env"])
                p_cap = st.slider("Yetenek Skoru (1-10):", min_value=1, max_value=10, value=t_data["capability"])
                p_cost = st.number_input("1K Token Maliyeti ($):", min_value=0.0, max_value=1.0, value=float(t_data["cost"]), step=0.005, format="%.3f")
                p_local = st.checkbox("Yerel Sağlayıcı (Local)", value=t_data["local"])
                p_strengths = st.multiselect(
                    "Güçlü Olduğu Alanlar:",
                    ["chat", "coding", "reasoning", "fast", "search"],
                    default=t_data["strengths"],
                )

            submit_prov = st.form_submit_button("💾 Sağlayıcıyı Kaydet", type="primary")
            if submit_prov:
                if not p_name.strip() or not p_url.strip() or not p_model.strip():
                    st.warning("Lütfen ad, base_url ve model alanlarını doldurun.")
                else:
                    payload = {
                        "name": p_name.strip(),
                        "base_url": p_url.strip(),
                        "model": p_model.strip(),
                        "api_key": p_key.strip() if p_key.strip() else None,
                        "api_key_env": p_env.strip() if p_env.strip() else None,
                        "capability": int(p_cap),
                        "cost": float(p_cost),
                        "local": bool(p_local),
                        "strengths": p_strengths or ["chat"],
                    }
                    save_res = api_post("/providers", json_data=payload)
                    if save_res and save_res.get("status") == "ok":
                        st.success(f"'{p_name}' sağlayıcısı başarıyla kaydedildi!")
                        st.rerun()

    # 3. Alt Sekme: Kota Yönetimi
    with tab_c_quota:
        st.markdown("##### 📊 Model Kotaları & Sayaç Yönetimi")
        st.write("Her model ve ajan için kullanım limitlerini izleyin, dinamik limit belirleyin veya sayaçları sıfırlayın.")

        if current_quotas:
            for m_name, q in current_quotas.items():
                lim = q.get("limit", 1)
                usd = q.get("used", 0)
                unit = q.get("unit", "istek")
                pct = min(100, int((usd / lim) * 100)) if lim > 0 else 0

                q_col1, q_col2, q_col3 = st.columns([2, 4, 2])
                with q_col1:
                    st.markdown(f"**{m_name}**")
                    st.caption(f"{usd} / {lim} {unit} ({pct}%)")
                with q_col2:
                    st.progress(pct / 100.0)
                with q_col3:
                    if pct >= 100:
                        st.markdown("<span class='badge-danger'>Kota Doldu</span>", unsafe_allow_html=True)
                    elif pct >= 80:
                        st.markdown("<span class='badge-warning'>Kritik</span>", unsafe_allow_html=True)
                    else:
                        st.markdown("<span class='badge-success'>Uygun</span>", unsafe_allow_html=True)
                st.divider()

            col_q_set, col_q_rst = st.columns(2)
            with col_q_set:
                st.markdown("###### ⚙️ Kota Limiti Güncelle")
                target_q_model = st.selectbox("Model Seç:", list(current_quotas.keys()), key="target_q_model")
                new_limit_val = st.number_input(
                    "Yeni İstek Limiti:", min_value=1, max_value=50000, value=current_quotas[target_q_model]["limit"], step=50
                )
                if st.button("Kotayı Güncelle", key="btn_update_quota"):
                    res_lim = api_post("/quotas/limit", json_data={"model": target_q_model, "limit": int(new_limit_val)})
                    if res_lim and res_lim.get("status") == "ok":
                        st.success(f"{target_q_model} kotası {new_limit_val} olarak güncellendi!")
                        st.rerun()

            with col_q_rst:
                st.markdown("###### 🔄 Kota Sayacını Sıfırla")
                reset_choice = st.selectbox("Sıfırlanacak Model:", ["Tüm Modeller"] + list(current_quotas.keys()), key="reset_choice")
                if st.button("Sayacı Sıfırla", key="btn_reset_quota", type="secondary"):
                    payload_rst = {"model": None if reset_choice == "Tüm Modeller" else reset_choice}
                    res_rst = api_post("/quotas/reset", json_data=payload_rst)
                    if res_rst and res_rst.get("status") == "ok":
                        st.success(f"{reset_choice} kullanım sayacı sıfırlandı!")
                        st.rerun()
        else:
            st.info("Kota bilgisi alınamadı.")


# ===========================================================================
# SEKME 3: 🏎️ Donanım, Benchmark & Model İndir
# ===========================================================================
with tab_hw:
    st.subheader("🏎️ Donanım Analizi, Hız Testleri & Tek Tıkla Model İndir")
    st.write(
        "Bilgisayarınızın işlemci, bellek ve ekran kartı (VRAM) kapasitesine göre en ideal "
        "açık kaynak yapay zeka modellerini keşfedin, indirin ve gerçek token/saniye hızını ölçün."
    )

    # Donanım Kartları
    hw_data = api_get("/hardware/info", timeout=5)
    hw_dict = hw_data.get("info", {}) if hw_data else {}

    c_hw1, c_hw2, c_hw3, c_hw4 = st.columns(4)
    c_hw1.metric("İşlemci Çekirdeği", f"{hw_dict.get('cpu_cores', '-')} Çekirdek")
    c_hw2.metric("Sistem Belleği (RAM)", f"{hw_dict.get('ram_gb', '-')} GB")
    c_hw3.metric("Ekran Kartı (GPU)", f"{hw_dict.get('gpu_name') or 'Entegre / Yok'}")
    c_hw4.metric("GPU Belleği (VRAM)", f"{hw_dict.get('gpu_vram_gb', 0)} GB")

    st.divider()

    # Önerilen Modeller & Tek Tıkla İndirme
    st.markdown("##### 💡 Donanımınıza En Uygun Yerel Modeller")
    recs_res = api_get("/hardware/recommend", timeout=5)
    recs_list = recs_res.get("recommendations", []) if recs_res else []

    if recs_list:
        for idx, rec in enumerate(recs_list):
            r_col1, r_col2, r_col3 = st.columns([3, 5, 2])
            with r_col1:
                st.markdown(f"**{rec.get('model')}**")
                fit_text = rec.get("fit", "")
                st.caption(f"Uygunluk: `{fit_text}`")
            with r_col2:
                st.write(rec.get("reason", ""))
            with r_col3:
                pull_btn = st.button(f"📥 İndir ({rec.get('model')})", key=f"pull_rec_{idx}")
                if pull_btn:
                    with st.spinner(f"'{rec.get('model')}' indiriliyor (Ollama pull)... Lütfen bekleyin."):
                        pull_res = api_post("/hardware/pull-model", json_data={"model": rec.get("model")}, timeout=900)
                        if pull_res and pull_res.get("status") == "ok":
                            st.success(f"✅ {rec.get('model')} başarıyla indirildi!")
                        else:
                            st.error(f"İndirme başarısız: {pull_res.get('detail') if pull_res else 'Hata'}")
            st.write("")
    else:
        st.info("Öneri listesi alınamadı.")

    st.divider()

    # Benchmark Bölümü: Donanım Skoru & Gerçek LLM Hız Testi
    b_col1, b_col2 = st.columns(2)

    with b_col1:
        st.markdown("##### ⚡ Hızlı Donanım Skoru (CPU & Disk G/Ç)")
        st.write("İşlemcinizin matematiksel işlem gücünü ve geçici dosya yazma hızını 1-100 ölçeğinde puanlar.")
        if st.button("🚀 Donanım Benchmark'ını Çalıştır", key="btn_run_hw_bench"):
            with st.spinner("CPU ve Disk hız testi yapılıyor..."):
                bench_res = api_get("/hardware/benchmark", timeout=30)
                if bench_res and bench_res.get("status") == "ok":
                    b_data = bench_res.get("benchmark", {})
                    mb1, mb2 = st.columns(2)
                    mb1.metric("CPU Skoru", f"{b_data.get('cpu_score')}/100")
                    mb2.metric("Disk G/Ç Skoru", f"{b_data.get('disk_io_score')}/100")
                    st.caption(b_data.get("notes", ""))
                else:
                    st.error("Donanım testi çalıştırılamadı.")

    with b_col2:
        st.markdown("##### ⏱️ Gerçek LLM Çıkarım Hızı (Token / Saniye)")
        st.write("Yerel Ollama üzerinde model çalıştırarak gerçek üretim hızını, ilk token süresini (TTFT) ve gecikmeyi ölçer.")

        rec_model_names = [r["model"] for r in recs_list] if recs_list else ["llama3"]
        test_model = st.selectbox(
            "Test Edilecek Yerel Model:",
            list(dict.fromkeys(rec_model_names + ["llama3", "qwen2.5-coder:7b", "deepseek-r1:8b", "mistral"])),
            key="llm_bench_model",
        )

        if st.button("🏎️ Gerçek LLM Hızını Ölç", key="btn_run_llm_bench", type="primary"):
            with st.spinner(f"'{test_model}' modeliyle çıkarım testi yapılıyor..."):
                llm_bench_res = api_post("/hardware/llm-benchmark", json_data={"model": test_model}, timeout=120)
                if llm_bench_res and llm_bench_res.get("status") == "ok":
                    tps = llm_bench_res.get("tokens_per_sec", 0.0)
                    ttft = llm_bench_res.get("ttft_ms", 0.0)
                    tot = llm_bench_res.get("total_ms", 0.0)
                    toks = llm_bench_res.get("generated_tokens", 0)

                    st.success(f"'{test_model}' Testi Tamamlandı!")
                    m1, m2 = st.columns(2)
                    m1.metric("Hız (Token / sn)", f"{tps} tok/s")
                    m2.metric("İlk Token Gecikmesi (TTFT)", f"{ttft} ms")

                    m3, m4 = st.columns(2)
                    m3.metric("Toplam Süre", f"{tot} ms")
                    m4.metric("Üretilen Token", f"{toks} token")

                    with st.expander("📝 Test Çıktısı"):
                        st.write(llm_bench_res.get("sample_output", ""))
                else:
                    st.error(f"LLM Hız Testi Hatası: {llm_bench_res.get('detail') if llm_bench_res else 'Ulaşılamadı'}")


# ===========================================================================
# SEKME 4: 📚 Model Kütüphanecisi (Librarian)
# ===========================================================================
with tab_lib:
    st.subheader("📚 Model Kütüphanecisi ve Yetenek Matrisi")
    st.write(
        "Açık kaynak ve bulut modellerini Kodlama, Akıl Yürütme, Hız ve Maliyet açısından 1-10 ölçeğinde "
        "kıyaslar. İsterseniz OpenRouter ve HuggingFace üzerinden **canlı internet taraması** yaparak güncel trendleri kataloğa ekler."
    )

    col_l1, col_l2, col_l3, col_l4 = st.columns([2, 2, 3, 2])
    with col_l1:
        task_choice = st.selectbox(
            "Görev Tipine Göre Sırala:",
            ["general", "coding", "reasoning", "chat", "fast"],
            format_func=lambda x: {
                "general": "Genel Yetenek (Tümü)",
                "coding": "Kodlama (Coding)",
                "reasoning": "Akıl Yürütme (Reasoning)",
                "chat": "Sohbet / Dokümantasyon",
                "fast": "Hız ve Maliyet Tasarrufu",
            }.get(x, x),
            key="lib_task_choice",
        )
    with col_l2:
        only_free = st.checkbox("Yalnızca Ücretsiz / Yerel", value=False, key="lib_only_free")
    with col_l3:
        include_online = st.checkbox(
            "🌐 Canlı İnternet Taraması Yap\n(OpenRouter + HuggingFace Trend GGUF)",
            value=False,
            key="lib_include_online",
            help="İşaretlenirse OpenRouter ücretsiz modelleri ve HuggingFace son 7 günün trend GGUF modelleri canlı taranır.",
        )
    with col_l4:
        st.write("")
        fetch_catalog = st.button("🔄 Kataloğu Getir / Yenile", type="primary", key="btn_fetch_catalog")

    if fetch_catalog or "lib_cached_models" not in st.session_state:
        spinner_msg = (
            "Model kataloğu taranıyor (OpenRouter & HuggingFace sorgulanıyor)..."
            if include_online
            else "Model kataloğu derleniyor..."
        )
        with st.spinner(spinner_msg):
            params = {
                "task_type": task_choice,
                "only_free": only_free,
                "include_online": include_online,
            }
            lib_res = api_get("/librarian/catalog", params=params, timeout=30)
            if lib_res and lib_res.get("status") == "ok":
                st.session_state["lib_cached_models"] = lib_res.get("models", [])
                st.session_state["lib_online_scanned"] = lib_res.get("online_scanned", False)

    cached_models = st.session_state.get("lib_cached_models", [])
    if cached_models:
        st.write(f"Katalogda Toplam **{len(cached_models)}** model listeleniyor:")

        table_rows = []
        for m in cached_models:
            table_rows.append(
                {
                    "Model": m.get("id"),
                    "Sağlayıcı": m.get("provider"),
                    "Yerel": "✅ Kurulu" if m.get("installed_locally") else ("💻 Yerel" if m.get("min_vram_gb", 0) > 0 else "☁️ Bulut"),
                    "Ücretsiz": "✅ Ücretsiz" if m.get("is_free_or_local") else "💲 Ücretli",
                    "Min VRAM": f"{m.get('min_vram_gb', 0)} GB",
                    "Toplam Puan": m.get("overall_score", 0),
                    "Kodlama": f"{m.get('coding')}/10",
                    "Akıl Yürütme": f"{m.get('reasoning')}/10",
                    "Sohbet": f"{m.get('chat')}/10",
                    "Hız": f"{m.get('speed')}/10",
                    "Maliyet Verimi": f"{m.get('cost_efficiency')}/10",
                }
            )

        st.dataframe(table_rows, use_container_width=True, hide_index=True)

        with st.expander("📥 Katalogdaki Bir Yerel Modeli Tek Tıkla İndir", expanded=False):
            local_candidate_models = [
                m["id"] for m in cached_models if m.get("provider") in ("Ollama", "HuggingFace (Trend)")
            ]
            if local_candidate_models:
                chosen_lib_model = st.selectbox("İndirmek İstediğiniz Model:", local_candidate_models)
                if st.button("Seçili Modeli İndir (Ollama)", key="btn_pull_lib_model"):
                    with st.spinner(f"'{chosen_lib_model}' indiriliyor..."):
                        p_res = api_post("/hardware/pull-model", json_data={"model": chosen_lib_model}, timeout=900)
                        if p_res and p_res.get("status") == "ok":
                            st.success(f"{chosen_lib_model} başarıyla indirildi!")
                        else:
                            st.error(f"İndirme başarısız: {p_res.get('detail') if p_res else 'Hata'}")
            else:
                st.caption("Katalogda indirilebilir yerel model bulunamadı.")
    else:
        st.info("Katalog listesi bulunamadı. Lütfen 'Kataloğu Getir / Yenile' butonuna tıklayın.")


# ===========================================================================
# SEKME 5: 🔭 Teknoloji Gözcüsü (Tech Scout)
# ===========================================================================
with tab_scout:
    st.subheader("🔭 Teknoloji Gözcüsü & Sistem İyileştirme Raporu")
    st.write(
        "Sisteminizin donanımını, Python kütüphanelerini ve kurulu CLI ajanlarını denetleyerek "
        "optimizasyon fırsatlarını listeler. İsteğe bağlı olarak **GitHub Search API** üzerinden "
        "açık kaynak yapay zeka ajanları ve LLM orkestrasyonu trendlerini canlı getirir."
    )

    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        scout_online = st.checkbox(
            "🌐 Canlı GitHub Açık Kaynak AI Trendlerini Getir",
            value=False,
            key="scout_online_chk",
            help="GitHub üzerindeki güncel popüler LLM yönlendirme, MCP ve otonom ajan projelerini çeker.",
        )
    with col_s2:
        run_scout = st.button("🔍 Raporu Çalıştır / Yenile", type="primary", key="btn_run_scout")

    if run_scout or "scout_cached_report" not in st.session_state:
        spinner_scout = "Sistem denetleniyor ve GitHub taranıyor..." if scout_online else "Sistem denetleniyor..."
        with st.spinner(spinner_scout):
            scout_res = api_get("/scout/report", params={"include_online": scout_online}, timeout=25)
            if scout_res and scout_res.get("status") == "ok":
                st.session_state["scout_cached_report"] = scout_res

    cached_scout = st.session_state.get("scout_cached_report", {})
    if cached_scout:
        summary = cached_scout.get("summary", {})

        s_col1, s_col2, s_col3, s_col4 = st.columns(4)
        s_col1.metric("Kurulu CLI Ajanları", f"{summary.get('installed_cli_count', 0)} Adet")
        s_col2.metric("Ekran Kartı & VRAM", f"{summary.get('gpu') or 'Yok'} ({summary.get('vram_gb', 0)} GB)")
        s_col3.metric("Sistem Belleği", f"{summary.get('ram_gb', '-')} GB")
        s_col4.metric("Tespit Edilen Öneri", f"{summary.get('findings_count', 0)} Adet")

        st.divider()

        # Sistem Bulguları ve Eylemler
        st.markdown("##### 📌 Sistem Analiz Bulguları ve Eylem Planı")
        findings = cached_scout.get("findings", [])
        if findings:
            for f in findings:
                prio = f.get("priority", "bilgi").lower()
                badge_class = "badge-danger" if prio == "yüksek" else ("badge-warning" if prio == "orta" else "badge-info")
                prio_label = prio.upper()

                st.markdown(
                    f"#### <span class='{badge_class}'>[{prio_label}]</span> {f.get('title')}",
                    unsafe_allow_html=True,
                )
                st.write(f.get("recommendation", ""))
                cmd = f.get("action_command")
                if cmd:
                    st.caption("Önerilen Hızlı Kurulum / Çalıştırma Komutu:")
                    st.code(cmd, language="bash")
                st.divider()
        else:
            st.success("Sisteminizde herhangi bir eksik veya optimizasyon ihtiyacı tespit edilmedi!")

        # Python Paket Denetimi
        with st.expander("📦 Python Paket Durumları ve Bağımlılıklar", expanded=False):
            packages = cached_scout.get("packages", [])
            if packages:
                pkg_rows = []
                for p in packages:
                    pkg_rows.append(
                        {
                            "Paket Adı": p.get("package"),
                            "Durum": "✅ Kurulu" if p.get("installed") else "❌ Kurulu Değil",
                            "Sürüm": p.get("version") or "Yok",
                            "İşlev": p.get("role"),
                            "Tür": "Zorunlu" if p.get("required") else "İsteğe Bağlı",
                        }
                    )
                st.dataframe(pkg_rows, use_container_width=True, hide_index=True)

        # GitHub Açık Kaynak AI Trendleri
        if scout_online:
            st.markdown("##### 🌟 Canlı GitHub Açık Kaynak AI & Ajan Trendleri")
            trends = cached_scout.get("github_trends", [])
            if trends:
                for repo in trends:
                    r_c1, r_c2 = st.columns([3, 1])
                    with r_c1:
                        st.markdown(f"**[{repo.get('full_name')}]({repo.get('url')})**")
                        st.write(repo.get("description") or "Açıklama belirtilmemiş.")
                        topics = repo.get("topics", [])
                        if topics:
                            st.caption(f"Etiketler: `{', '.join(topics)}`")
                    with r_c2:
                        st.metric("⭐ Yıldız", f"{repo.get('stars', 0):,}")
                    st.divider()
            else:
                st.info("GitHub trendleri alınamadı veya liste boş döndü.")
    else:
        st.info("Henüz Tech Scout raporu oluşturulmadı. Lütfen 'Raporu Çalıştır / Yenile' butonuna tıklayın.")
