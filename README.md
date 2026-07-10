# TradeOps AI

An AI-powered trade operations investigation system. Given a failed trade ID, an autonomous AI agent retrieves the trade record, execution logs, and relevant operational policies, then generates a structured investigation report: root cause, supporting evidence, confidence score, and recommended next steps.

---

## Problem

In financial operations, failed trades create immediate downstream risk: settlement penalties, counterparty disputes, regulatory reporting obligations, and reputational damage. Investigating the root cause of a failure today requires an analyst to manually cross-reference three separate systems: the order management system, the execution log archive, and the policy manual before they can even begin drafting a resolution. This process takes hours and is highly error-prone under time pressure.

TradeOps AI compresses that workflow into under 30 seconds by deploying an autonomous agent that does the cross-referencing automatically and returns a structured, evidence-backed report.

---

## What It Does

1. **Accepts a Trade ID** from the operations team
2. **Retrieves the trade record** (instrument, counterparty, notional, failure type)
3. **Retrieves the full execution log** (timestamped event chain from order receipt to failure)
4. **Searches policy documents** (RAG over 10 operational policy docs) for rules relevant to the failure type
5. **Generates a structured report** containing:
   - Root cause (one-sentence summary)
   - Supporting evidence (3–5 specific log entries and policy clauses)
   - Confidence score (0–100%, model-assessed based on evidence clarity)
   - Recommended next steps (actionable resolution steps for the ops team)

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **LLM** | `gpt-oss-120b` | Reasoning, tool calling, report generation |
| **Embeddings** | `nomic-embed-text-v1.5` | Semantic search over policy documents |
| **Agent framework** | LangGraph | ReAct-style tool-calling loop with structured output |
| **MCP tools** | LangChain `@tool` | Modular tools for trade data and policy retrieval |
| **Vector store** | ChromaDB (local, persistent) | Stores embedded policy documents for RAG |
| **Database** | SQLite + SQLAlchemy | Stores trades and execution logs |
| **API** | FastAPI + Uvicorn | REST backend that runs the investigation workflow |
| **Frontend** | Streamlit | Trade browser and investigation report UI |
| **Data generation** | Faker | Deterministic synthetic dataset |

---

## Architecture

```
Streamlit UI  (port 8501)
      │  HTTP POST /investigate/{trade_id}
      ▼
FastAPI Backend  (port 8000)
      │  invoke
      ▼
LangGraph Agent
      │
      ├── get_trade_details  ──▶  SQLite (trades table)
      ├── get_execution_logs ──▶  SQLite (execution_logs table)
      └── search_policies    ──▶  ChromaDB (policies collection)
                                       │
                                  nomic-embed-text-v1.5
                                  (University API)
      │
      ▼
  write_report node
      │  gpt-oss-120b generates structured JSON
      ▼
InvestigationReport
  { root_cause, evidence[], confidence_score, recommended_next_steps[] }
```

### LangGraph Workflow

The agent runs a **ReAct loop**: the LLM decides which tool to call next, receives the result, and repeats until it has called all three tools. It then exits the loop and a dedicated `write_report` node asks the LLM to synthesise the gathered evidence into a structured JSON report validated by Pydantic.

```
START → agent → tools → agent → tools → agent → write_report → END
                  ↑_______________|
                  (loops until no more tool calls)
```

---

## Synthetic Dataset

The project ships with a fully generated dataset seeded deterministically:

| Dataset | Count | Details |
|---|---|---|
| Trades | 50 | 20 FAILED, 20 SETTLED, 10 PENDING |
| Execution logs | 200 | 4–5 per trade, realistic event chains |
| Policy documents | 10 | Multi-paragraph operational policies covering settlement, margin, compliance, counterparty risk, penalties, BCP, and reference data |

**Failure types covered:** `INSUFFICIENT_MARGIN`, `SETTLEMENT_BREACH`, `COUNTERPARTY_REJECTION`, `INSTRUMENT_MISMATCH`, `PRICE_TOLERANCE_BREACH`, `DUPLICATE_TRADE`, `COMPLIANCE_HOLD`, `NETWORK_TIMEOUT`, `CUSTODIAN_REJECTION`, `CURRENCY_MISMATCH`

---

## Project Structure

```
TradeOps-AI/
├── data/
│   ├── synthetic.py        # Generates all trades, logs, and policy docs
│   ├── seed_db.py          # Seeds SQLite from synthetic data
│   └── seed_chromadb.py    # Embeds and stores policy docs in ChromaDB
├── mcp_tools/
│   ├── db.py               # Shared SQLAlchemy engine
│   ├── trade_details.py    # get_trade_details tool
│   ├── execution_logs.py   # get_execution_logs tool
│   └── policy_search.py    # search_policies tool (RAG)
├── workflow/
│   ├── state.py            # LangGraph state + InvestigationReport schema
│   └── graph.py            # LangGraph graph definition + investigate()
├── api/
│   ├── schemas.py          # FastAPI request/response models
│   └── main.py             # FastAPI app (/health, /trades, /investigate)
├── frontend/
│   └── app.py              # Streamlit UI
├── chroma_db/              # ChromaDB local persist directory (gitignored)
├── tradeops.db             # SQLite database (gitignored)
├── .env                    # Local secrets (gitignored)
├── .env.example            # Environment variable template
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.12+
- Access to an OpenAI-compatible LLM API (tested with the University of Florida AI gateway)
- No database server required — SQLite runs embedded with no setup

### 1. Clone and install

```bash
git clone <repo-url>
cd TradeOps-AI
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
OPENAI_BASE_URL=https://your-api-gateway/v1
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-oss-120b            # or any tool-calling model available to you
EMBEDDING_MODEL=nomic-embed-text-v1.5

DATABASE_URL=sqlite:///./tradeops.db
CHROMA_PERSIST_DIR=./chroma_db
```

### 3. Seed the databases

Run both seed scripts once from the project root:

```bash
python3 data/seed_db.py        # creates tradeops.db with 50 trades + 200 logs
python3 data/seed_chromadb.py  # embeds 10 policy docs into ChromaDB
```

### 4. Run the application

Open two terminals from the project root:

**Terminal 1 — API server:**
```bash
python3 -m uvicorn api.main:app --port 8000
```

**Terminal 2 — UI:**
```bash
streamlit run frontend/app.py
```

Then open **http://localhost:8501** in your browser.

---

## Usage

1. In the sidebar, set the **Filter by status** dropdown to `FAILED`
2. Select any trade from the list — the preview card shows instrument, notional, counterparty, and failure type
3. Click **Run Investigation**
4. The report appears in the main panel within ~30 seconds

The **Run Investigation** button is disabled for `SETTLED` and `PENDING` trades.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/trades` | List all 50 trades with metadata |
| `POST` | `/investigate/{trade_id}` | Run a full AI investigation for a failed trade |

Interactive docs available at **http://localhost:8000/docs** while the API server is running.
