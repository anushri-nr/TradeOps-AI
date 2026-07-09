"""MCP tool: semantic search over operational policy documents via ChromaDB + RAG."""

import os
import chromadb
from openai import OpenAI
from langchain_core.tools import tool
from dotenv import load_dotenv

load_dotenv()

_chroma_client = None
_openai_client: OpenAI | None = None


def _get_chroma_collection():
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        )
    return _chroma_client.get_collection("policies")


def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL"),
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    return _openai_client


def _embed(text: str) -> list[float]:
    response = _get_openai_client().embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text-v1.5"),
        input=text,
    )
    return response.data[0].embedding


@tool
def search_policies(query: str) -> str:
    """
    Search operational policy documents for content relevant to a trade failure.
    Accepts a natural language query describing the failure scenario (e.g.
    'settlement deadline missed', 'margin shortfall', 'counterparty rejected trade').
    Returns the top 3 most relevant policy excerpts with their document titles.
    Use this to find the applicable rules, procedures, and escalation steps.
    """
    query_embedding = _embed(query)
    collection = _get_chroma_collection()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=3,
        include=["documents", "metadatas"],
    )

    docs = results["documents"][0]
    metas = results["metadatas"][0]

    if not docs:
        return "No relevant policy documents found for the given query."

    sections = []
    for doc, meta in zip(docs, metas):
        excerpt = doc.strip()[:1200]  # cap at ~300 tokens per policy
        sections.append(
            f"--- {meta['doc_id']}: {meta['title']} ---\n{excerpt}"
        )

    return f"Top {len(sections)} relevant policy sections:\n\n" + "\n\n".join(sections)
