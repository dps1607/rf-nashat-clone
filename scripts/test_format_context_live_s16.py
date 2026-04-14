"""Live retrieval test — query rf_reference_library for 'egg health',
feed the chunks to the real format_context(), print the output.

Read-only: no Chroma writes, no chunk modification. Uses the actual
604 chunks currently in the local database.
"""
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Load .env for OPENAI_API_KEY
from dotenv import load_dotenv
load_dotenv(REPO / ".env")

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from rag_server.app import format_context

ef = OpenAIEmbeddingFunction(
    api_key=os.environ["OPENAI_API_KEY"],
    model_name="text-embedding-3-large",
)
client = chromadb.PersistentClient(path="/Users/danielsmith/Claude - RF 2.0/chroma_db")
col = client.get_collection("rf_reference_library", embedding_function=ef)

query = "How do I optimize egg health and ovulation?"
hits = col.query(query_texts=[query], n_results=6, include=["metadatas", "documents"])

# Pack into format_context's expected shape
chunks = []
for i in range(len(hits["ids"][0])):
    chunks.append({
        "source": "rf_reference_library",
        "text": hits["documents"][0][i],
        "metadata": hits["metadatas"][0][i],
    })

# Classify what we got
v3_count = sum(1 for c in chunks if c["metadata"].get("v3_category"))
a4m_count = sum(1 for c in chunks if c["metadata"].get("module_number"))
other = len(chunks) - v3_count - a4m_count
print(f"retrieved {len(chunks)} chunks: {v3_count} v3, {a4m_count} A4M, {other} other\n")

out = format_context(chunks)
print("=" * 70)
print("format_context() output on live retrieval:")
print("=" * 70)
print(out)
print("=" * 70)
print(f"length: {len(out)} chars")
print()
print("quick sanity:")
print(f"  contains 'REFERENCE KNOWLEDGE': {('REFERENCE KNOWLEDGE' in out)}")
print(f"  contains at least one 'Source:' line: {('Source:' in out)}")
print(f"  contains at least one 'Link:' line: {('Link:' in out)}")
print(f"  contains at least one 'Module' line: {('Module ' in out)}")
bad1 = "Source: \n" in out
bad2 = "Source:  " in out
print(f"  no blank citation rows (empty Source:): {(not bad1 and not bad2)}")
