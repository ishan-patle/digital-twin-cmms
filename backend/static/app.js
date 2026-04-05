import * as THREE from 'https://esm.sh/three@0.160.1';
import * as OBC from 'https://esm.sh/@thatopen/components@2.4.11';

// 3D VIEWER INITIALIZATION
let highlighter;
let fragmentManager;

async function initViewer() {
    try {
        const container = document.getElementById('viewer-container');
        const components = new OBC.Components();
        components.init();

        const worlds = components.get(OBC.Worlds);
        const world = worlds.create();
        world.uuid = world.uuid || "main-world-123";
        world.name = "Main World";
        
        world.scene = new OBC.SimpleScene(components);
        world.renderer = new OBC.SimpleRenderer(components, container);
        world.camera = new OBC.SimpleCamera(components);
        
        world.scene.setup();
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        world.scene.three.add(ambientLight);

        world.camera.controls.setLookAt(20, 20, 20, 0, 0, 0);

        fragmentManager = components.get(OBC.FragmentsManager);
        const fragmentIfcLoader = components.get(OBC.IfcLoader);
        
        fragmentIfcLoader.settings.wasm = {
            path: "https://unpkg.com/web-ifc@0.0.56/",
            absolute: true
        };
        await fragmentIfcLoader.setup();

        console.log("Loading 3D Digital Twin...");
        const file = await fetch('/sample_mep.ifc');
        const data = await file.arrayBuffer();
        const buffer = new Uint8Array(data);
        const model = await fragmentIfcLoader.load(buffer);
        window.ifcModel = model;
        world.scene.three.add(model);
        
        world.camera.controls.fitToSphere(model, true);
        
        try {
            highlighter = components.get(OBC.Highlighter);
            highlighter.setup({ world });
        } catch(he) {
            console.error("Highlighter setup warning:", he);
        }
        
        console.log("Digital Twin loaded successfully.");
    } catch(e) {
        console.error("FATAL ERROR IN VIEWER:", e);
        document.getElementById('viewer-container').innerHTML = `<h1 style='color:red'>Crash: ${e.message}</h1>`;
    }
}

// Highlight Logic Pipeline from Streamlit
function highlightElements(expressIds) {
    if(!highlighter || !window.ifcModel) return;
    
    // Clear any previous highlights via highlighter.clear() if needed.
    // 'select' is the default property injected by Highlighter setup
    highlighter.clear("select");

    console.log("Streamlit dispatched HIGHLIGHT target ExpressIDs:", expressIds);
    const numericIds = expressIds.map(id => parseInt(id, 10)).filter(id => !isNaN(id));
    
    if (numericIds.length > 0) {
        try {
            const itemMap = window.ifcModel.getFragmentMap(numericIds);
            // Highlight the selection
            highlighter.highlightByID("select", itemMap, true, true);
        } catch(e) {
            console.error("Highlighting failed to map IDs", e);
        }
    }
}

window.addEventListener('message', (event) => {
    // Only accept highlight events
    if (event.data && event.data.type === 'highlight') {
        highlightElements(event.data.guids);
    }
});

// Start
initViewer();
