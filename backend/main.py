from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import os
import re

from backend.data_ingestor import ingest_text_document
from backend.smart_agent import get_agent
from langchain_core.messages import HumanMessage

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    if not os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_API_KEY") == "nvapi-your-key-here":
        return {
            "reply": "Error: Please update your NVIDIA_API_KEY in the `.env` file to activate the AI.",
            "highlights": []
        }
        
    try:
        agent = get_agent()
        state = {"messages": [HumanMessage(content=req.message)]}
        result = agent.invoke(state)
        
        final_message = result["messages"][-1].content
        
        highlights = re.findall(r'\[HIGHLIGHT:(.*?)\]', final_message)
        cleaned_message = re.sub(r'\[HIGHLIGHT:.*?\]', '', final_message).strip()
        
        return {
            "reply": cleaned_message,
            "highlights": highlights
        }
    except Exception as e:
        return {"reply": f"System Alert: Agent processing failed: {str(e)}", "highlights": []}

@app.post("/api/upload_doc")
async def upload_doc(file: UploadFile = File(...)):
    content = await file.read()
    try:
        text_content = content.decode('utf-8')
    except Exception:
        text_content = content.decode('latin-1')
        
    ingest_text_document(text_content, source_name=file.filename)
    return {"status": "success", "message": f"Ingested {file.filename} into Knowledge Base."}

@app.get("/sample_mep.ifc")
async def get_ifc_model():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "data", "sample_mep.ifc"))

# Mount static files for the frontend
app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")
