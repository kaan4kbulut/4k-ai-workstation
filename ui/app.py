import requests
import streamlit as st

API_BASE = "http://localhost:8000"

st.set_page_config(page_title="Nexus AI Studio", layout="wide")

st.title("🚀 Nexus AI Studio Kontrol Paneli")

# Kenar çubuğu - durum bilgisi
st.sidebar.header("Sistem Durumu")
registered_models: list[str] = []
try:
    status_res = requests.get(f"{API_BASE}/status", timeout=5).json()
    st.sidebar.success(f"Sunucu: {status_res['status']}")
    registered_models = status_res.get("registered_models", [])
    st.sidebar.write("**Aktif Sağlayıcılar & Ajanlar:**")
    for m in registered_models:
        st.sidebar.markdown(f"- `{m}`")
    with st.sidebar.expander("Kota Durumu"):
        st.json(status_res.get("quotas", {}))
except Exception:
    st.sidebar.error("Sunucuya ulaşılamıyor")

with st.sidebar.expander("Donanım & Öneriler", expanded=True):
    try:
        info = requests.get(f"{API_BASE}/hardware/info", timeout=5).json()
        r = requests.get(f"{API_BASE}/hardware/recommend", timeout=5).json()
        hw = info.get("info", {})
        st.write(
            f"**CPU:** {hw.get('cpu_cores')} Çekirdek | **RAM:** {hw.get('ram_gb')} GB\n\n"
            f"**GPU:** {hw.get('gpu_name') or 'Yok'} ({hw.get('gpu_vram_gb') or 0} GB VRAM)"
        )
        st.write("**Önerilen Yerel Modeller:**")
        for rec in r.get("recommendations", []):
            st.markdown(f"- **{rec['model']}** ({rec['fit']}) — {rec['reason']}")
    except Exception:
        st.write("Donanım bilgisi alınamadı.")

tab_cmd, tab_cli, tab_lib, tab_scout = st.tabs(
    [
        "⚡ Komut Merkezi",
        "🛠️ CLI Ajanları & Abonelikler",
        "📚 Model Kütüphanecisi (Librarian)",
        "🔭 Teknoloji Gözcüsü (Tech Scout)",
    ]
)

with tab_cmd:
    st.subheader("Komut Merkezi")
    user_prompt = st.text_area(
        "İsteğini yaz:",
        placeholder="Örnek: Bu Python fonksiyonunu optimize et ve birim testlerini yaz...",
    )
    is_parallel = st.checkbox("Paralel Çalıştırma (Görevi Böl ve Dağıt)", value=False)
    selected_model = st.selectbox("Model / Ajan Seç:", ["auto", *registered_models] or ["auto"])

    if st.button("Çalıştır"):
        if not user_prompt:
            st.warning("Lütfen bir istek yaz.")
        else:
            with st.spinner("Çalışıyor..."):
                try:
                    payload = {
                        "prompt": user_prompt,
                        "model": selected_model,
                        "parallel": is_parallel,
                    }
                    response = requests.post(
                        f"{API_BASE}/query", json=payload, timeout=300
                    ).json()

                    st.markdown("### Yanıt")
                    if response.get("type") == "parallel":
                        st.info(f"Görev {response['sub_tasks_count']} alt göreve bölündü.")
                        for task_id, result in response["responses"].items():
                            with st.expander(f"Alt görev {task_id} — {result['model']}"):
                                st.write(result["response"])
                    else:
                        st.write(response.get("response"))
                        st.caption(f"Kullanılan model/ajan: {response.get('model')}")
                except Exception as e:
                    st.error(f"Hata: {e}")

with tab_cli:
    st.subheader("CLI Araçları ve Abonelik Ajanları")
    try:
        cli_res = requests.get(f"{API_BASE}/cli/tools", timeout=5).json()
        for tool in cli_res.get("tools", []):
            badge = "✅ Kurulu" if tool["installed"] else "⚪ Kurulu Değil"
            with st.expander(f"{badge} — **{tool['name']}** ({tool['subscription_type']})"):
                st.write(f"**Rol:** {tool['role']}")
                st.write(f"**Güçlü Alanlar:** `{', '.join(tool['strengths'])}`")
                if tool["installed"]:
                    st.code(tool["binary_path"], language="text")
                else:
                    st.info(f"Kurulum komutu: `{tool['install_hint']}`")
    except Exception as e:
        st.error(f"CLI araçları listelenemedi: {e}")

with tab_lib:
    st.subheader("Model Kütüphanecisi ve Yetenek Matrisi")
    task_choice = st.selectbox(
        "Görev Tipine Göre Sırala:",
        ["general", "coding", "reasoning", "chat", "fast"],
    )
    only_free = st.checkbox("Yalnızca Ücretsiz / Yerel Modelleri Göster", value=False)
    try:
        lib_res = requests.get(
            f"{API_BASE}/librarian/catalog",
            params={"task_type": task_choice, "only_free": only_free},
            timeout=10,
        ).json()
        models = lib_res.get("models", [])
        if models:
            st.dataframe(models, use_container_width=True)
    except Exception as e:
        st.error(f"Katalog yüklenemedi: {e}")

with tab_scout:
    st.subheader("Teknoloji Gözcüsü & Sistem İyileştirme Raporu")
    try:
        scout_res = requests.get(f"{API_BASE}/scout/report", timeout=10).json()
        for finding in scout_res.get("findings", []):
            st.markdown(f"#### [{finding['priority'].upper()}] {finding['title']}")
            st.write(finding["recommendation"])
            if finding.get("action_command"):
                st.code(finding["action_command"], language="bash")
    except Exception as e:
        st.error(f"Tech Scout raporu alınamadı: {e}")
