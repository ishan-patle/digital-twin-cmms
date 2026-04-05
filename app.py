import streamlit as st
import os
import re
import time
import streamlit.components.v1 as components
from dotenv import load_dotenv

# Ensure the paths and envs are handled
load_dotenv()
from backend.smart_agent import get_agent, build_system_message
from langchain_core.messages import HumanMessage, SystemMessage
from backend.data_ingestor import ingest_text_document

st.set_page_config(layout="wide", page_title="Digital Twin CMMS")

st.title("🎛️ Digital Twin CMMS Dashboard")

st.markdown("""
Welcome to the Property Manager interface. 
Make sure your FastAPI server is running in the background (`python -m uvicorn backend.main:app`) so the 3D Viewer iframe renders!
""")

col1, col2 = st.columns([3, 2])

with col1:
    st.subheader("3D Facility Viewer")
    # Streamlit component mounting the standalone IFC visualizer
    # Using ?v=2 or a random seed ensures the browser doesn't load a cached version of the old UI
    components.iframe(f"http://localhost:8000/viewer.html?v={int(time.time())}", height=650)
    
    # Broadcast any active highlights from the chat state strictly to the interactive 3D viewer
    if "active_highlights" in st.session_state and st.session_state.active_highlights:
        guids_array = str(st.session_state.active_highlights)
        js_code = f"""
        <script>
            // Ping the highlight payload blindly down to all frames to avoid Cross-Origin DOM inspection blocks
            const payload = {{
                type: 'highlight',
                guids: {guids_array}
            }};
            for (let i = 0; i < window.parent.frames.length; i++) {{
                try {{
                    window.parent.frames[i].postMessage(payload, '*');
                }} catch(e) {{}}
            }}
        </script>
        """
        components.html(js_code, height=0, width=0)

with col2:
    st.subheader("Assistant & Knowledge Base")
    tab1, tab2 = st.tabs(["💬 AI Chat", "📄 Document Manager"])
    
    with tab1:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! I'm your facility twin assistant. What maintenance issues can I help with today?"}
            ]
            
        for msg in st.session_state.messages:
            st.chat_message(msg["role"]).write(msg["content"])
            
        if prompt := st.chat_input("E.g: Show me all ventilation terminals... or What is in the Vaskerom?"):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.chat_message("user").write(prompt)
            
            with st.spinner("Analyzing model and documentation..."):
                try:
                    agent = get_agent()
                    state = {"messages": [build_system_message(), HumanMessage(content=prompt)]}
                    res = agent.invoke(state)
                    reply = res["messages"][-1].content
                    
                    # Optional: Parse out highlights
                    highlights = re.findall(r'\[HIGHLIGHT:(.*?)\]', reply)
                    cleaned_reply = re.sub(r'\[HIGHLIGHT:.*?\]', '', reply).strip()
                    
                    st.session_state.messages.append({"role": "assistant", "content": cleaned_reply})
                    if highlights:
                        parsed_ids = []
                        for h in highlights:
                            parsed_ids.extend([x.strip() for x in h.split(',')])
                        st.session_state.active_highlights = parsed_ids
                        
                    st.rerun() # Immediately re-render to trigger the injected script
                except Exception as e:
                    st.error(f"Error accessing Agent: {str(e)}")

    with tab2:
        st.write("Upload operations & maintenance documents. The AI will learn them instantly.")
        file = st.file_uploader("Upload Specs or Manuals", type=["txt"])
        if file:
            content = file.read().decode('utf-8')
            ingest_text_document(content, file.name)
            st.success(f"Ingested `{file.name}` successfully into the knowledge base!")
