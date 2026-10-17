import streamlit as st
import requests

st.set_page_config(page_title="Nexus AI Studio", layout="wide")

st.title("🚀 Nexus AI Studio Control Panel")

# Sidebar for Status
st.sidebar.header("System Status")
try:
    status_res = requests.get("http://localhost:8000/status").json()
    st.sidebar.success(f"Server: {status_res['status']}")
    st.sidebar.write("**Available Models:**")
    for m in status_res['registered_models']:
        st.sidebar.markdown(f"- {m}")
except:
    st.sidebar.error("Server Offline")

# Main Chat Interface
st.subheader("Command Center")
user_prompt = st.text_area("Enter your prompt:", placeholder="Example: Optimize this Python function...")
is_parallel = st.checkbox("Parallel Execution (Split Task)", value=False)
selected_model = st.selectbox("Select Model:", ["auto", "Ollama"])

if st.button("Execute"):
    if user_prompt:
        with st.spinner("Executing..."):
            try:
                payload = {"prompt": user_prompt, "model": selected_model, "parallel": is_parallel}
                response = requests.post(
                    "http://localhost:8000/query", 
                    json=payload
                ).json()
                
                st.markdown("### Response")
                if response.get("type") == "parallel":
                    st.info(f"Task decomposed into {response['sub_tasks_count']} parallel sub-tasks.")
                    for task_id, res in response['responses'].items():
                        with st.expander(f"Sub-task {task_id}"):
                            st.write(res)
                else:
                    st.write(response['response'])
                    st.caption(f"Used model: {response.get('model')}")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Please enter a prompt.")
