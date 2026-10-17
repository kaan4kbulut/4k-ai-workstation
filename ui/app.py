import requests
import streamlit as st

st.set_page_config(page_title="Nexus AI Studio", layout="wide")

st.title("🚀 Nexus AI Studio Kontrol Paneli")

# Kenar çubuğu - durum bilgisi
st.sidebar.header("Sistem Durumu")
registered_models: list[str] = []
try:
    status_res = requests.get("http://localhost:8000/status", timeout=5).json()
    st.sidebar.success(f"Sunucu: {status_res['status']}")
    registered_models = status_res.get("registered_models", [])
    st.sidebar.write("**Kullanılabilir Modeller:**")
    for m in registered_models:
        st.sidebar.markdown(f"- {m}")
    with st.sidebar.expander("Kota"):
        st.json(status_res.get("quotas", {}))
except Exception:
    st.sidebar.error("Sunucuya ulaşılamıyor")

# Ana komut arayüzü
st.subheader("Komut Merkezi")
user_prompt = st.text_area("İsteğini yaz:", placeholder="Örnek: Bu Python fonksiyonunu optimize et...")
is_parallel = st.checkbox("Paralel Çalıştırma (Görevi Böl)", value=False)
selected_model = st.selectbox("Model Seç:", ["auto", *registered_models] or ["auto"])

if st.button("Çalıştır"):
    if not user_prompt:
        st.warning("Lütfen bir istek yaz.")
    else:
        with st.spinner("Çalışıyor..."):
            try:
                payload = {"prompt": user_prompt, "model": selected_model, "parallel": is_parallel}
                response = requests.post(
                    "http://localhost:8000/query", json=payload, timeout=300
                ).json()

                st.markdown("### Yanıt")
                if response.get("type") == "parallel":
                    st.info(f"Görev {response['sub_tasks_count']} alt göreve bölündü.")
                    for task_id, result in response["responses"].items():
                        with st.expander(f"Alt görev {task_id} — {result['model']}"):
                            st.write(result["response"])
                else:
                    st.write(response.get("response"))
                    st.caption(f"Kullanılan model: {response.get('model')}")
            except Exception as e:
                st.error(f"Hata: {e}")
