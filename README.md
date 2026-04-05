# 🏗️ Digital Twin CMMS

An AI-powered **Computerized Maintenance Management System** that combines a 3D BIM model viewer with a LangGraph ReAct agent for intelligent facility management.

Built with **FastAPI**, **Streamlit**, **LangGraph**, **NVIDIA NIM**, and **IFC.js (ThatOpen Components)**.

---

## ✨ Features

- **3D IFC Model Viewer** — Interactive WebGL rendering of BIM/IFC models using ThatOpen Components (Three.js)
- **AI Chat Assistant** — LangGraph ReAct agent backed by NVIDIA NIM that understands the building model
- **Structured IFC Queries** — Query elements by type, room, system, keyword, or GlobalId — no embeddings needed for the 3D model
- **Document Knowledge Base** — Upload maintenance manuals and specs; the AI indexes them via FAISS + NVIDIA Embeddings for RAG
- **Cross-Frame Highlighting** — Streamlit chat dispatches highlight commands to the 3D viewer iframe via `postMessage`

## 🏛️ Architecture

```
┌─────────────────────┐       ┌──────────────────────────────┐
│   Streamlit (app.py)│       │   FastAPI (backend/main.py)  │
│   ┌───────────────┐ │       │   ┌────────────────────────┐ │
│   │  AI Chat Tab  │ │       │   │  /api/chat             │ │
│   │  Doc Upload   │ │       │   │  /api/upload_doc       │ │
│   └───────────────┘ │       │   │  /sample_mep.ifc       │ │
│   ┌───────────────┐ │       │   └────────────────────────┘ │
│   │ 3D Viewer     │◄├──────►│   ┌────────────────────────┐ │
│   │ (iframe)      │ │       │   │  Static Frontend       │ │
│   └───────────────┘ │       │   │  index.html / app.js   │ │
└─────────────────────┘       │   └────────────────────────┘ │
                              └──────────┬───────────────────┘
                                         │
                    ┌────────────────────┬┴───────────────────┐
                    │                    │                     │
             ┌──────▼──────┐   ┌────────▼────────┐   ┌───────▼───────┐
             │  ifc_tools   │   │  smart_agent    │   │ data_ingestor │
             │  IFC Parser  │   │  LangGraph ReAct│   │ FAISS + NIM   │
             └──────────────┘   └─────────────────┘   └───────────────┘
```

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- [NVIDIA NIM API Key](https://build.nvidia.com/)

### Installation

```bash
git clone https://github.com/ishanoshada/digital-twin-cmms.git
cd digital-twin-cmms

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root:

```env
NVIDIA_API_KEY="nvapi-your-key-here"
```

### Running

**Terminal 1** — Start the FastAPI backend (serves 3D viewer + API):

```bash
python -m uvicorn backend.main:app --reload --port 8000
```

**Terminal 2** — Start the Streamlit frontend (chat + dashboard):

```bash
streamlit run app.py
```

Open **http://localhost:8501** for the full dashboard.

## 📁 Project Structure

```
digital_twin/
├── app.py                  # Streamlit chat + dashboard frontend
├── backend/
│   ├── __init__.py
│   ├── data_ingestor.py    # FAISS document ingestion & search
│   ├── ifc_tools.py        # IFC model parser & query engine
│   ├── main.py             # FastAPI server (API + static files)
│   ├── smart_agent.py      # LangGraph ReAct agent + tool definitions
│   └── static/
│       ├── app.js           # 3D viewer (Three.js + ThatOpen Components)
│       ├── index.html       # Standalone HTML frontend
│       ├── style.css        # Viewer styles
│       └── viewer.html      # Iframe target for Streamlit
└── data/
    └── sample_mep.ifc      # Sample IFC model (MEP/HVAC)
```

## 🚧 Work In Progress

### WIP 1 — 3D Model Highlighting on Element Discovery
> When the AI agent finds a component (e.g., a boiler or air terminal), the corresponding geometry should highlight in the 3D viewer in real time. Currently, the `postMessage` pipeline is wired up but ExpressID-to-fragment mapping needs hardening for all element types.

### WIP 2 — Robust LangGraph Agents
> The current single ReAct agent works but is limited. Planned improvements include multi-agent orchestration (supervisor + specialist agents), better tool-calling reliability, conversation memory across sessions, and streaming responses for a smoother UX.

### WIP 3 — Overall Bug Fixes
> General stability improvements including error handling for large IFC files, WASM loader fallback paths, CORS edge cases between Streamlit and FastAPI, and improved FAISS index persistence.

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| 3D Rendering | [ThatOpen Components](https://github.com/ThatOpen/engine_components) + Three.js |
| IFC Parsing | [IfcOpenShell](https://ifcopenshell.org/) (Python) + [web-ifc](https://github.com/ThatOpen/engine_web-ifc) (WASM) |
| AI / LLM | [NVIDIA NIM](https://build.nvidia.com/) (Llama 3.1 70B) |
| Agent Framework | [LangGraph](https://github.com/langchain-ai/langgraph) |
| Embeddings + RAG | NVIDIA NV-EmbedQA + FAISS |
| Backend | FastAPI |
| Frontend | Streamlit + Vanilla HTML/CSS/JS |

## 📄 License

This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)** — see the [LICENSE](LICENSE) file for details.

This means any modified version of this software that is accessible over a network **must** release its source code under the same license.
