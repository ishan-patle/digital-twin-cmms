"""
ifc_tools.py - Structural IFC Query Engine
===========================================
Strategy:
  1. At startup, parse the entire IFC file and build `_context` - a rich
     structured summary of every system, space, type-group and element.
  2. Expose this context as a string so the LLM's system prompt always knows
     EXACTLY what is in the model (types, counts, systems, rooms).
  3. Provide targeted query tools the LLM can call to drill down:
       - get_elements_by_type(ifc_class)
       - get_elements_in_space(space_name)
       - get_element_details(global_id)
       - search_elements_by_keyword(keyword)   ← exact substring on all props
  No embeddings, no vector search for the IFC - just clean structured queries.
"""
import os
import json
import ifcopenshell

IFC_FILE = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample_mep.ifc')

# ── Global caches built once at startup ────────────────────────────────────
_model = None
_elements: dict[str, dict] = {}   # GlobalId → rich dict
_type_index: dict[str, list] = {} # IfcClass → [GlobalId, ...]
_space_index: dict[str, list] = {}# RoomName → [GlobalId, ...]
_systems: list[dict] = []         # IfcSystem groups
_model_context_str: str = ""       # injected into system prompt


# ── Load & Parse ────────────────────────────────────────────────────────────

def _get_all_psets(element) -> dict:
    """Return dict of all property sets → {prop_name: value}."""
    psets = {}
    for rel in getattr(element, 'IsDefinedBy', []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue
        pset = rel.RelatingPropertyDefinition
        pset_name = getattr(pset, 'Name', 'Unknown')
        props = {}
        for prop in getattr(pset, 'HasProperties', []):
            val = getattr(prop, 'NominalValue', None)
            props[prop.Name] = val.wrappedValue if hasattr(val, 'wrappedValue') else str(val)
        if props:
            psets[pset_name] = props
    return psets


def _build_rich_element(e) -> dict:
    """Build a rich dict for a single IFC element."""
    psets = _get_all_psets(e)
    
    # Flatten all props into a single searchable string blob
    flat_props = {}
    for pset_props in psets.values():
        flat_props.update(pset_props)

    # Try to find human-readable name from common prop keys
    label = (
        getattr(e, 'Name', None)
        or flat_props.get('Beskrivelse')       # Norwegian: Description
        or flat_props.get('Description')
        or flat_props.get('Produkt nr.', '').strip()
        or e.is_a()
    )

    return {
        "GlobalId":   e.GlobalId,
        "ExpressId":  e.id(),
        "Class":      e.is_a(),
        "Label":      label,
        "ProductNo":  flat_props.get('Produkt nr.', ''),
        "Room":       flat_props.get('Rom navn', ''),
        "RoomNo":     flat_props.get('Rom nr.', ''),
        "Prosjekt":   flat_props.get('Prosjektnavn', ''),
        "AllProps":   flat_props,  # every property, flattened
        "Psets":      psets,       # organised by Pset name
    }


def _load_and_index():
    """Parse the IFC file once and build all indexes."""
    global _model, _elements, _type_index, _space_index, _systems, _model_context_str

    print("[ifc_tools] Parsing IFC file …")
    _model = ifcopenshell.open(IFC_FILE)

    _elements = {}
    _type_index = {}

    # Scan EVERY product in the model. Index elements that have Pset_DDS
    # (this model's standard property set), using their EXACT class — no supertype stomping.
    for e in _model.by_type('IfcProduct'):
        psets = _get_all_psets(e)
        if not psets:
            continue  # skip geometry-only elements with zero properties
        rich = _build_rich_element(e)
        rich['Psets'] = psets  # ensure psets attached
        _elements[e.GlobalId] = rich
        exact_cls = e.is_a()
        _type_index.setdefault(exact_cls, []).append(e.GlobalId)

    # Space index
    _space_index = {}
    for gid, eq in _elements.items():
        room = eq.get("Room", "").strip()
        if room:
            _space_index.setdefault(room, []).append(gid)

    # IfcSystem / IfcGroup
    _systems = []
    for sys in _model.by_type('IfcSystem'):
        members = []
        for rel in getattr(sys, 'IsGroupedBy', []):
            for m in getattr(rel, 'RelatedObjects', []):
                if m.GlobalId in _elements:
                    members.append(m.GlobalId)
        _systems.append({
            "Name": getattr(sys, 'Name', ''),
            "Description": getattr(sys, 'Description', ''),
            "Members": members,
        })

    # Build context string for the LLM system prompt dynamically from the DATA itself
    type_summary_lines = []
    for cls, ids in sorted(_type_index.items(), key=lambda x: -len(x[1])):
        labels_counts = {}
        for gid in ids:
            lbl = _elements[gid].get('Label', '')
            if lbl and str(lbl).strip() and not str(lbl).startswith('Ifc'):
                labels_counts[lbl] = labels_counts.get(lbl, 0) + 1
        
        top_labels = sorted(labels_counts.items(), key=lambda x: -x[1])[:6]
        example_str = ", ".join(f"'{lbl}'" for lbl, c in top_labels)
        if example_str:
            type_summary_lines.append(f"  - {cls}: {len(ids)} elements. Discovered labels: {example_str}")
        else:
            type_summary_lines.append(f"  - {cls}: {len(ids)} elements.")
            
    type_summary = "\n".join(type_summary_lines)

    top_spaces = sorted(_space_index.items(), key=lambda x: -len(x[1]))[:25]
    space_summary_lines = []
    for space, ids in top_spaces:
        classes = list(set(_elements[gid]['Class'].replace('Ifc','') for gid in ids))[:4]
        space_summary_lines.append(f"  - '{space}' ({len(ids)} items: {','.join(classes)}...)")
    space_summary = "\n".join(space_summary_lines)
    sys_summary = "\n".join(
        f"  - {s['Name'] or '(unnamed)'}: {len(s['Members'])} elements"
        for s in _systems[:20]
    ) or "  (none found)"

    _model_context_str = f"""
=== LOADED IFC MODEL: SGD Blueberry HVAC ===
Total indexed MEP elements: {len(_elements)}

Element types in the model:
{type_summary}

Rooms/Spaces with assigned elements (sample):
{space_summary or '(rooms not assigned in this model)'}

IfcSystem groups:
{sys_summary}

IMPORTANT: All elements are stored internally. Use the tools to query them precisely.
Use get_elements_by_type() to find all of a type, get_element_details() for a specific item.
""".strip()

    print(f"[ifc_tools] Indexed {len(_elements)} elements, {len(_type_index)} types, {len(_systems)} systems.")


# ── Public API ──────────────────────────────────────────────────────────────

def ensure_loaded():
    if not _elements:
        _load_and_index()


def get_model_context() -> str:
    ensure_loaded()
    return _model_context_str


def get_elements_by_type(ifc_class: str) -> list[dict]:
    """Return all elements of the given IFC class (e.g. 'IfcBoiler', 'IfcFlowTerminal')."""
    ensure_loaded()
    ids = _type_index.get(ifc_class, [])
    return [_elements[i] for i in ids]


def get_elements_in_space(space_name: str) -> list[dict]:
    """Return all elements whose room name matches (case-insensitive partial)."""
    ensure_loaded()
    q = space_name.lower()
    results = []
    for room, ids in _space_index.items():
        if q in room.lower():
            results.extend(_elements[i] for i in ids)
    return results


def get_element_details(global_id: str) -> dict | None:
    """Return the full rich dict for a specific GlobalId."""
    ensure_loaded()
    return _elements.get(global_id)


def search_elements_by_keyword(keyword: str) -> list[dict]:
    """
    Exact substring search across ALL property keys AND values of every element.
    Use this as a fallback when you know a product code or description fragment.
    """
    ensure_loaded()
    q = keyword.lower()
    results = []
    for eq in _elements.values():
        # Build blob from BOTH keys and values so 'Produkt nr.' and 'OSO' both work
        blob_parts = []
        for k, v in eq["AllProps"].items():
            blob_parts.append(str(k))
            blob_parts.append(str(v))
        blob = " ".join(blob_parts).lower()
        if q in blob or q in str(eq["Label"]).lower():
            results.append(eq)
    return results[:10]


def get_all_element_types() -> list[str]:
    """Return all IFC classes present in the model."""
    ensure_loaded()
    return sorted(_type_index.keys())


def get_all_systems() -> list[dict]:
    """Return all IfcSystem groups with their member counts."""
    ensure_loaded()
    return _systems
