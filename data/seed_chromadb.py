"""
Embeds the 10 policy documents using the university embedding API
and stores them in a local ChromaDB collection.
Run once after seed_db.py.
"""

import os
import chromadb
from openai import OpenAI
from dotenv import load_dotenv
from synthetic import get_all_data

load_dotenv()

COLLECTION_NAME = "policies"


def get_embedding(client: OpenAI, text: str) -> list[float]:
    response = client.embeddings.create(
        model=os.getenv("EMBEDDING_MODEL", "nomic-embed-text-v1.5"),
        input=text,
    )
    return response.data[0].embedding


def seed():
    _, _, policies = get_all_data()

    llm_client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    chroma_client = chromadb.PersistentClient(
        path=os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
    )

    # Drop and recreate so re-runs are idempotent
    existing = [c.name for c in chroma_client.list_collections()]
    if COLLECTION_NAME in existing:
        chroma_client.delete_collection(COLLECTION_NAME)
    collection = chroma_client.create_collection(COLLECTION_NAME)

    ids, embeddings, documents, metadatas = [], [], [], []

    for doc in policies:
        print(f"  Embedding {doc['doc_id']}: {doc['title']} ...")
        embedding = get_embedding(llm_client, doc["content"])
        ids.append(doc["doc_id"])
        embeddings.append(embedding)
        documents.append(doc["content"])
        metadatas.append({"title": doc["title"], "doc_id": doc["doc_id"]})

    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
    print(f"\nStored {len(ids)} policy documents in ChromaDB collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    seed()
