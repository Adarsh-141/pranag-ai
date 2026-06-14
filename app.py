"""
PRANAG-AI  —  Streamlit front-end for the Prompt Parser

Run:
    streamlit run app.py
"""
import json
import streamlit as st
import os
# 1. Force HuggingFace completely offline before any other imports occur
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from search_engine.vector_store import populate
from orchestrator.workflow import run_pipeline
import logging
# Ensure the root logger is set to INFO so your timers appear
logging.basicConfig(level=logging.INFO)

# ── One-time initialisation ───────────────────────────────────────────────────


import json
import streamlit as st
import logging

from search_engine.vector_store import populate
from orchestrator.workflow import run_pipeline

# Ensure the root logger is set to INFO so your timers appear
logging.basicConfig(level=logging.INFO)

# ── One-time initialisation (Warmup Phase) ──────────────────────────────────
@st.cache_resource(show_spinner="Warming up PRANAG-AI Engine (Preloading Models & DB)...")
def init():
    # 1. Open disk files and map ChromaDB index into RAM
    populate()
    
    # 2. Force-load SentenceTransformer weights into memory right now
    from search_engine.embeddings import get_embedding_model
    _ = get_embedding_model() 
    
    # 3. Establish a persistent HTTP session to eliminate handshake overhead later
    import requests
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

# Execute warmup immediately on startup and keep the global session ready
http_session = init()

# ── UI ────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="PRANAG-AI Prompt Parser", page_icon="🌾", layout="centered")
st.title("🌾 PRANAG-AI — Prompt Parser")
st.caption("Convert a natural language crop prompt into a structured `spec.json` for the simulation pipeline.")

with st.form("prompt_form"):
    prompt = st.text_area(
        "Enter your crop design prompt",
        placeholder='e.g. "I need wheat that can survive 48°C heat in Jodhpur with low rainfall"',
        height=100,
    )
    submitted = st.form_submit_button("🚀 Generate Spec")

if submitted and prompt.strip():
    with st.spinner("Running PRANAG pipeline …"):
        result = run_pipeline(prompt.strip())

    pipeline_id = result.get("pipeline_id", "—")
    spec        = result.get("spec")
    error       = result.get("error")

    st.divider()
    st.subheader("Pipeline Result")
    st.caption(f"Pipeline ID: `{pipeline_id}`")

    if spec:
        col1, col2, col3 = st.columns(3)
        col1.metric("Crop",        spec.get("crop", "—").title())
        col2.metric("Location",    spec.get("location", "—"))
        col3.metric("Temperature", f"{spec.get('temperature', '—')} °C")

        with st.expander("📋 Full spec.json", expanded=True):
            st.json(spec)

        if spec.get("retrieved_traits"):
            with st.expander("🔬 Retrieved traits"):
                for t in spec["retrieved_traits"]:
                    st.markdown(f"- {t}")

        if spec.get("scientific_basis"):
            with st.expander("📚 Scientific basis"):
                for f in spec["scientific_basis"]:
                    st.markdown(f"- {f}")

        confidence = spec.get("confidence", 0)
        st.progress(confidence, text=f"Confidence: {confidence:.0%}")

    else:
        st.error(f"Pipeline failed: {error or 'Unknown error'}")
        st.info("Make sure Ollama is running:  `ollama serve`  and the model is pulled.")

elif submitted:
    st.warning("Please enter a prompt before generating.")
