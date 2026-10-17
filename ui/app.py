import requests
import streamlit as st

st.set_page_config(page_title="Nexus AI Studio", layout="wide")

st.title("🚀 Nexus AI Studio Control Panel")

# Sidebar for Status
st.sidebar.header("System Status")
registered_models: list[str] = []
try:
    status_res = requests.get("http://localhost:8000/status", timeout=5).json()
    st.sidebar.success(f"Server: {status_res['status']}")
    registered_models = status_res.get("registered_models", [])
    st.sidebar.write("**Available Models:**")
    for m in registered_models:
        st.sidebar.markdown(f"- {m}")
    with st.sidebar.expander("Quota"):
        st.json(status_res.get("quotas", {}))
except Exception:
    st.sidebar.error("Server Offline")

# Main Chat Interface
st.subheader("Command Center")
user_prompt = st.text_area("Enter your prompt:", placeholder="Example: Optimize this Python function...")
is_parallel = st.checkbox("Parallel Execution (Split Task)", value=False)
selected_model = st.selectbox("Select Model:", ["auto", *registered_models] or ["auto"])

if st.button("Execute"):
    if not user_prompt:
        st.warning("Please enter a prompt.")
    else:
        with st.spinner("Executing..."):
            try:
                payload = {"prompt": user_prompt, "model": selected_model, "parallel": is_parallel}
                response = requests.post(
                    "http://localhost:8000/query", json=payload, timeout=300
                ).json()

                st.markdown("### Response")
                if response.get("type") == "parallel":
                    st.info(f"Task decomposed into {response['sub_tasks_count']} parallel sub-tasks.")
                    for task_id, result in response["responses"].items():
                        with st.expander(f"Sub-task {task_id} — {result['model']}"):
                            st.write(result["response"])
                else:
                    st.write(response.get("response"))
                    st.caption(f"Used model: {response.get('model')}")
            except Exception as e:
                st.error(f"Error: {e}")
