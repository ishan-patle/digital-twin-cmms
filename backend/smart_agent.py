"""
smart_agent.py - LangGraph ReAct Agent for Digital Twin CMMS
=============================================================
The agent receives the full IFC model summary in its system prompt, so it
already "knows" what types, rooms, and systems exist before calling any tool.

Tools:
  - list_ifc_element_types       → what classes exist in the model
  - get_elements_by_type         → all elements of an IFC class
  - get_elements_in_space        → elements in a named room/space
  - get_element_details          → full property dump for one GlobalId
  - search_elements_by_keyword   → fallback substring search on all props
  - list_ifc_systems             → IfcSystem groups and their sizes
  - search_maintenance_documents → knowledge base (user-uploaded manuals)
"""
import json
import os
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import SystemMessage

from backend.ifc_tools import (
    ensure_loaded,
    get_model_context,
    get_all_element_types,
    get_elements_by_type,
    get_elements_in_space,
    get_element_details,
    search_elements_by_keyword,
    get_all_systems,
)
from backend.data_ingestor import search_maintenance_kb


# ── Pre-load IFC on module import ───────────────────────────────────────────
ensure_loaded()


# ── Tools ───────────────────────────────────────────────────────────────────

@tool
def list_ifc_element_types() -> str:
    """
    Returns all IFC element classes that exist in the loaded 3D model.
    Always call this first to understand what types of equipment are available.
    """
    types = get_all_element_types()
    return "Available IFC types in model:\n" + "\n".join(f"  - {t}" for t in types)


@tool
def get_elements_by_type_tool(ifc_class: str) -> str:
    """
    Returns all elements of the specified IFC class.
    Example inputs: 'IfcBoiler', 'IfcFlowTerminal', 'IfcEnergyConversionDevice',
    'IfcPump', 'IfcValve', 'IfcSanitaryTerminal', 'IfcAirTerminal'.
    Use list_ifc_element_types first to see what classes exist.
    Returns Label, ProductNo, Room, GlobalId for each element.
    """
    elements = get_elements_by_type(ifc_class)
    if not elements:
        return f"No elements of type '{ifc_class}' found."
    # Return a clean summary, not the full prop dump
    summary = []
    for e in elements[:15]:
        summary.append({
            "GlobalId": e["GlobalId"],
            "ExpressId": e["ExpressId"],
            "Label": e["Label"],
            "ProductNo": e["ProductNo"],
            "Room": e["Room"] or e["RoomNo"],
        })
    return json.dumps(summary, ensure_ascii=False)


@tool
def get_elements_in_space_tool(space_name: str) -> str:
    """
    Returns all MEP elements located in a specific room or space.
    Example: 'Disponibelt', 'Bad', 'Teknisk rom', or a room number like '0-4-1-7-4'.
    """
    elements = get_elements_in_space(space_name)
    if not elements:
        return f"No elements found in space matching '{space_name}'."
    summary = [{"GlobalId": e["GlobalId"], "ExpressId": e["ExpressId"], "Label": e["Label"], "Class": e["Class"]} for e in elements[:15]]
    return json.dumps(summary, ensure_ascii=False)


@tool
def get_element_details_tool(global_id: str) -> str:
    """
    Returns complete property details for a specific element identified by its GlobalId.
    Use this after locating an element to get its full spec sheet: size, pressure,
    manufacturer, installation height etc.
    """
    elem = get_element_details(global_id)
    if not elem:
        return f"Element with GlobalId '{global_id}' not found."
    return json.dumps({
        "GlobalId": elem["GlobalId"],
        "ExpressId": elem["ExpressId"],
        "Class": elem["Class"],
        "Label": elem["Label"],
        "ProductNo": elem["ProductNo"],
        "Room": elem["Room"],
        "RoomNo": elem["RoomNo"],
        "AllProperties": elem["AllProps"],
    }, ensure_ascii=False)


@tool
def search_elements_by_keyword_tool(keyword: str) -> str:
    """
    Searches all element properties for a keyword.
    Use this when you know a partial product code, Norwegian description fragment,
    or any text that might appear in the model's metadata.
    Example: 'WWB 200', 'bereder', 'GU-001', 'sluk'.
    """
    results = search_elements_by_keyword(keyword)
    if not results:
        return f"No elements with keyword '{keyword}' in their properties."
    summary = [{"GlobalId": e["GlobalId"], "ExpressId": e["ExpressId"], "Label": e["Label"], "ProductNo": e["ProductNo"]} for e in results]
    return json.dumps(summary, ensure_ascii=False)


@tool
def list_ifc_systems_tool() -> str:
    """
    Returns all IfcSystem groups in the model (e.g., HVAC systems, plumbing loops).
    Use this to understand larger system groupings in the building.
    """
    systems = get_all_systems()
    if not systems:
        return "No IfcSystem groups found in the model."
    summary = [{"Name": s["Name"], "Description": s["Description"], "MemberCount": len(s["Members"])} for s in systems]
    return json.dumps(summary, ensure_ascii=False)


@tool
def search_maintenance_documents(query: str) -> str:
    """
    Searches the uploaded maintenance manuals and specification documents.
    Use for questions about service intervals, replacement procedures, part numbers,
    warranty info, or any textual maintenance guidance.
    """
    snippets = search_maintenance_kb(query)
    if not snippets:
        return "No maintenance documents uploaded yet. Please inform the user they can upload specs in the DocManager tab."
    return "\n\n".join(snippets)


# ── Agent Factory ───────────────────────────────────────────────────────────

def get_agent():
    llm = ChatNVIDIA(model="meta/llama-3.1-70b-instruct")

    tools = [
        list_ifc_element_types,
        get_elements_by_type_tool,
        get_elements_in_space_tool,
        get_element_details_tool,
        search_elements_by_keyword_tool,
        list_ifc_systems_tool,
        search_maintenance_documents,
    ]

    return create_react_agent(llm, tools)


def build_system_message() -> SystemMessage:
    """Builds the system message injecting real model context."""
    model_ctx = get_model_context()
    content = f"""You are 'Digital Twin Assistant', an expert AI for Property Managers.
You have full knowledge of the loaded BIM model, shown below. Use this to answer questions accurately.

{model_ctx}

TOOLS GUIDE:
1. list_ifc_element_types → Run this first to see what types exist.
2. get_elements_by_type_tool(ifc_class) → Get all elements of a type.
3. get_elements_in_space_tool(space_name) → Find equipment in a room.
4. get_element_details_tool(global_id) → Full property sheet for one element.
5. search_elements_by_keyword_tool(keyword) → Search by product code.
6. list_ifc_systems_tool → See HVAC/plumbing system groups.
7. search_maintenance_documents(query) → Search uploaded manuals.

CRITICAL RULES FOR SEARCHING:
- If the user asks for a semantic concept (like "hot water unit", "vent", "pipe", "heater"), DO NOT use `search_elements_by_keyword_tool`. The data is in Norwegian so English words won't match. INSTEAD, look at the IFC classes provided above, pick the correct class (e.g. 'IfcEnergyConversionDevice'), and call `get_elements_by_type_tool(ifc_class)`.
- Use `search_elements_by_keyword_tool` ONLY for exact Product Numbers, manufacturer names (e.g. OSO), or exact room parts if asked.
- When you identify an element in the model, ALWAYS include [HIGHLIGHT:<ExpressId>] in your reply (e.g., [HIGHLIGHT:1234]). If there are multiple, optionally output [HIGHLIGHT:1234,5678].
- Never use jargon like 'IFC node' or 'GlobalId'. Say 'the model'.
- Be concise and professional.
"""
    return SystemMessage(content=content)
