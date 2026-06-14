# PRANAG-AI — Prompt Parser

Converts a natural language prompt into a structured `spec.json` for the simulation pipeline. Accepts plain English text from a file, CLI argument, or interactive input, and runs it through a 5-node LangGraph pipeline that parses, searches, researches, builds, and validates the output.

---

## Project Structure

```
Prompt-Parser-AI-main/
├── input_folder/
│   └── input.txt              # ← put your prompt here
├── orchestrator/
│   ├── prompt_parser.py       # LLM + regex parsing (Node 1)
│   ├── research_fetcher.py    # Semantic Scholar API (Node 3)
│   ├── spec_builder.py        # assembles final spec dict (Node 4)
│   ├── output_validator.py    # Pydantic validation (Node 5)
│   ├── output_exporter.py     # saves spec.json to disk (Node 5)
│   └── workflow.py            # LangGraph pipeline definition
├── search_engine/
│   ├── vector_store.py        # ChromaDB wrapper + seed traits
│   ├── similarity_search.py   # cosine similarity search
│   ├── embeddings.py          # sentence-transformers model
│   └── data_cleaner.py        # text normalisation utilities
├── shared/
│   ├── config.py              # all settings via .env
│   └── models.py              # Pydantic models (ParsedPrompt, Spec)
├── outputs/                   # generated spec.json files land here
├── chroma_db/                 # ChromaDB persisted on disk
├── main.py                    # CLI entry point
├── app.py                     # Streamlit UI entry point
├── requirements.txt
└── .env.example
```

---

## Prerequisites

- Python 3.11 or 3.12
- [Ollama](https://ollama.com) installed and running locally
- DeepSeek-R1:7b model pulled in Ollama

---

## Setup

**1. Clone and create a virtual environment**

```bash
git clone <repo-url>
cd Prompt-Parser-AI-main
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Copy and fill in the environment file**

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=deepseek-r1:7b
OLLAMA_TIMEOUT=120

# Optional — get a free key at https://www.semanticscholar.org/product/api
SEMANTIC_SCHOLAR_API_KEY=

OUTPUT_DIR=./outputs
EXPORT_TO_FILE=true

# Leave blank until simulation team shares their URL
SRIKAR_ENDPOINT=
```

**4. Pull the LLM model**

```bash
ollama pull deepseek-r1:7b
ollama serve
```

---

## Running the Pipeline

### Option 1 — File input (primary method)

Place your English prompt inside `input_folder/input.txt`:

```
wheat for Jodhpur at 48°C with low rainfall, drought resistant
```

Then run:

```bash
python main.py
```

> **Windows note:** Do not use PowerShell `echo` to write the file — it saves as UTF-16 which causes a decode error. Instead open the file in Notepad and save it, or use:
> ```powershell
> [System.IO.File]::WriteAllText("input_folder\input.txt", "your prompt here", [System.Text.Encoding]::UTF8)
> ```

### Option 2 — CLI argument

```bash
python main.py "wheat for Jodhpur at 48°C with low rainfall"
```

### Option 3 — Streamlit UI

```bash
streamlit run app.py
```

Open `http://localhost:8501` in your browser, type a prompt, and click **Generate Spec**.

**Input priority order:** CLI argument → `input_folder/input.txt` → interactive terminal prompt.

---

## How the Pipeline Works

```
input_folder/input.txt
        │
        ▼
  [1. parse_node]  ── prompt_parser.py
        │              Regex fallback + Ollama LLM (DeepSeek-R1)
        │              Output: parsed dict {crop, location, temperature, ...}
        ▼
  [2. search_node] ── similarity_search.py + ChromaDB
        │              Embeds query → cosine search over trait database
        │              Output: top-10 relevant trait strings
        ▼
  [3. research_node] ── research_fetcher.py
        │               Queries Semantic Scholar API for recent papers
        │               Output: list of {title, key_finding, url, year}
        ▼
  [4. build_node]  ── spec_builder.py
        │              Merges parsed + traits + research into spec dict
        │              Computes confidence score
        ▼
  [5. validate_node] ── output_validator.py + output_exporter.py
                        Pydantic schema check → saves outputs/spec_*.json
                        Optionally POSTs to simulation endpoint
```

If validation fails, the pipeline retries from Node 1 up to 3 times. The pipeline never fully crashes — regex fallback guarantees a parsed result even when Ollama is offline, and hardcoded research fallbacks handle Semantic Scholar downtime.

---

## Output — spec.json

Every successful run writes a file to `./outputs/` named `spec_YYYYMMDD_HHMMSS_<uuid>.json`.

Example output:

```json
{
  "crop": "wheat",
  "location": "Jodhpur, Rajasthan",
  "temperature": 48.0,
  "humidity": null,
  "rainfall": 300.0,
  "soil_type": "sandy loam",
  "stress_conditions": ["extreme heat stress", "drought"],
  "target_traits": ["heat tolerance", "drought resistance", "deep root system"],
  "retrieved_traits": [
    "heat shock protein HSP70 expression increases wheat survival above 45°C",
    "deep root architecture in wheat reaching 120cm for subsoil moisture access"
  ],
  "scientific_basis": ["Wheat yield under heat stress reduced by 6% per °C above 30°C..."],
  "research_titles": ["Heat stress tolerance mechanisms in wheat"],
  "research_sources": ["https://api.semanticscholar.org/..."],
  "research_years": [2023],
  "constraints": {},
  "confidence": 0.87,
  "pipeline_version": "1.0.0",
  "generated_at": "2026-05-28T14:45:16.123456+00:00"
}
```

---

## Configuration Reference

All settings are in `shared/config.py` and can be overridden via `.env`:

| Setting | Default | Description |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | LLM model name |
| `OLLAMA_TIMEOUT` | `120` | Seconds before LLM call times out |
| `SEMANTIC_SCHOLAR_API_KEY` | _(empty)_ | Optional — avoids rate limiting |
| `OUTPUT_DIR` | `./outputs` | Where spec.json files are saved |
| `EXPORT_TO_FILE` | `true` | Set `false` to skip disk write |
| `SRIKAR_ENDPOINT` | _(empty)_ | Simulation team's POST endpoint |
| `CHROMA_PERSIST_DIR` | `./chroma_db` | ChromaDB storage path |
| `SEARCH_TOP_K` | `10` | Number of traits to retrieve |
| `MAX_RETRIES` | `3` | Pipeline retry limit on validation failure |

---

## Connecting to the Simulation Team

Once the simulation team (Srikar/Aryan) shares their endpoint URL, set it in `.env`:

```env
SRIKAR_ENDPOINT=http://srikar-sim:8000/spec
```

The pipeline will automatically POST the validated spec after each successful run alongside saving it to disk.

---

## Scaling the Search Engine

The vector store currently has 47 hardcoded seed traits. To load a larger dataset:

```python
from search_engine.vector_store import get_collection
from search_engine.embeddings import embed_batch
import csv, uuid

col = get_collection()
texts, ids, metas = [], [], []

with open("your_data.csv") as f:
    for row in csv.DictReader(f):
        texts.append(row["text"])
        ids.append(str(uuid.uuid4()))
        metas.append({"crop": row["crop"], "domain": row["domain"]})

vectors = [v.tolist() for v in embed_batch(texts)]
col.upsert(ids=ids, documents=texts, embeddings=vectors, metadatas=metas)
```

The orchestrator's `search_node` picks up new entries automatically on the next run — no pipeline changes needed.

---

## Team
Ashirwad, Om and Shambhavi
