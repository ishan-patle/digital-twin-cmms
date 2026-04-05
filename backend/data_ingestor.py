import os
from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

VECTOR_STORE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'faiss_index')

def get_embeddings():
    # Use full namespace for NIM embedding model
    return NVIDIAEmbeddings(model="nvidia/nv-embedqa-e5-v5")

def ingest_text_document(text_content: str, source_name: str):
    """
    Ingests raw text into the document knowledge base.
    Called by the FastAPI upload endpoint.
    """
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    chunks = splitter.create_documents([text_content], metadatas=[{"source": source_name}])
    
    embeddings = get_embeddings()
    
    if os.path.exists(VECTOR_STORE_PATH):
        vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
        vector_store.add_documents(chunks)
    else:
        vector_store = FAISS.from_documents(chunks, embeddings)
        
    vector_store.save_local(VECTOR_STORE_PATH)

def search_maintenance_kb(query: str, k=3):
    """
    Searches the FAISS DB for relevant text about maintenance.
    """
    if not os.path.exists(VECTOR_STORE_PATH):
        return ["No maintenance documents have been uploaded yet. Inform the user they can upload specs in the DocManager tab."]
        
    embeddings = get_embeddings()
    vector_store = FAISS.load_local(VECTOR_STORE_PATH, embeddings, allow_dangerous_deserialization=True)
    docs = vector_store.similarity_search(query, k=k)
    return [d.page_content for d in docs]
    
