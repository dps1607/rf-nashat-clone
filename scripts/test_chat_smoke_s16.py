"""Step 10 confidence check — end-to-end /chat smoke against nashat_sales.
Hits the real Flask handler via test client. No server lifecycle to manage.

Expected behavior:
  - Retrieves 6-8 chunks (5ish v3 Egg Health + 1-2 A4M)
  - format_context renders mixed shape cleanly
  - Sonnet 4.6 reads the context, writes a grounded response
  - Response does NOT contain "Dr. Christina" or "Massinople"
  - Response SHOULD cite specifics the human could verify
"""
import os
import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# .env sourcing (OPENAI_API_KEY + ANTHROPIC_API_KEY)
from dotenv import load_dotenv
load_dotenv(REPO / ".env")

from rag_server.app import app

client = app.test_client()

question = "I'm trying to improve my egg quality before starting IVF. What should I actually focus on?"

print("=" * 70)
print(f"QUESTION: {question}")
print("=" * 70)

resp = client.post(
    "/chat",
    data=json.dumps({
        "question": question,
        "history": [],
        "mode": "public_default",
    }),
    content_type="application/json",
)

print(f"\nstatus: {resp.status_code}")
if resp.status_code != 200:
    print("ERROR:", resp.get_data(as_text=True))
    sys.exit(1)

body = resp.get_json()
print(f"agent: {body.get('agent_id')}")
print(f"mode:  {body.get('mode')}")
print(f"chunks retrieved: {body.get('chunk_count')}")
print()
print("=" * 70)
print("RESPONSE TEXT")
print("=" * 70)
print(body.get("response", ""))
print()
print("=" * 70)
print("SAFETY + QUALITY CHECKS")
print("=" * 70)

text = body.get("response", "")
text_lower = text.lower()

checks = [
    ("no 'Dr. Christina' leaked", "christina" not in text_lower),
    ("no 'Massinople' leaked", "massinople" not in text_lower),
    ("no 'Dr. Chris' (the coach handle) leaked", "dr. chris " not in text_lower and "dr.chris " not in text_lower),
    ("response is non-empty", len(text) > 100),
    ("response is grounded (mentions supplementation or nutrition)", any(w in text_lower for w in ["supplement", "nutrition", "vitamin", "coq10", "diet", "prenatal"])),
    ("response does not start with ERROR", not text.startswith("[ERROR]")),
]
for label, ok in checks:
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")

# Also check if citation hint (Source: or Link:) appears — Sonnet may or may
# not surface them naturally; this is informational, not pass/fail.
has_source_echo = "egg health guide" in text_lower
print(f"  [info] response mentions 'Egg Health Guide' by name: {has_source_echo}")
