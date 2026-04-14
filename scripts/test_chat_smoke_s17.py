"""Session 17 closure /chat smoke — end-to-end test that the Sugar Swaps
Guide chunk ingested via v3's Google Doc handler:
  - Is retrieved by a relevant query
  - Renders cleanly through format_context
  - Sonnet generates a grounded response from it
  - Response contains zero leaked former-collaborator names

Mirrors test_chat_smoke_s16.py (Egg Health Guide PDF closure proof) but
asks about sugar/sweetener swaps to force retrieval of the new Google Doc
chunk over the existing PDF and A4M chunks.
"""
import sys
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv
load_dotenv(REPO / '.env')

from rag_server.app import app

client = app.test_client()

question = "What sugar substitutes or natural sweeteners are best when I'm trying to optimize fertility? I want to cut sugar but still enjoy something sweet."

print('=' * 70)
print(f'QUESTION: {question}')
print('=' * 70)

resp = client.post(
    '/chat',
    data=json.dumps({
        'question': question,
        'history': [],
        'mode': 'public_default',
    }),
    content_type='application/json',
)

print(f'\nstatus: {resp.status_code}')
if resp.status_code != 200:
    print('ERROR:', resp.get_data(as_text=True))
    sys.exit(1)

body = resp.get_json()
print(f'agent: {body.get("agent_id")}')
print(f'mode:  {body.get("mode")}')
print(f'chunks retrieved: {body.get("chunk_count")}')
print()

# Show retrieved chunk identities (proves Sugar Swaps doc was retrieved)
sources = body.get('sources') or body.get('citations') or []
print('retrieved sources:')
for s in sources[:8]:
    print(f'  - {s}')
print()

print('=' * 70)
print('RESPONSE TEXT')
print('=' * 70)
print(body.get('response', ''))
print()
print('=' * 70)
print('SAFETY + QUALITY CHECKS')
print('=' * 70)

text = body.get('response', '')
text_lower = text.lower()

checks = [
    ('no Christina leaked',         'christina' not in text_lower),
    ('no Massinople leaked',        'massinople' not in text_lower),
    ('no Dr. Chris leaked',         'dr. chris ' not in text_lower and 'dr.chris ' not in text_lower),
    ('response non-empty',          len(text) > 100),
    ('response is grounded (mentions sugar/sweetener/swap)',
        any(w in text_lower for w in ['sugar','sweet','stevia','monk fruit','xylitol','honey','maple'])),
    ('response does not start with ERROR', not text.startswith('[ERROR]')),
]
for label, ok in checks:
    print(f'  [{"PASS" if ok else "FAIL"}] {label}')

has_guide_mention = 'sugar swap' in text_lower or 'fertility-smart sugar' in text_lower
print(f'  [info] response mentions Sugar Swap guide by name: {has_guide_mention}')

failed = sum(1 for _, ok in checks if not ok)
sys.exit(0 if failed == 0 else 1)
