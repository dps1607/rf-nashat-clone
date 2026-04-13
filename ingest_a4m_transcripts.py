#!/usr/bin/env python3
"""
A4M Reference Library — Transcript Ingestion (PILOT)
======================================================
Copies Haiku-chunking approach from rag_pipeline_v3_llm.py, adapts
for A4M lecture format (SPK_N speaker headers) and reference-library
metadata schema.

PILOT MODE: Module 1 only. Writes chunks to JSON for inspection.
NO ChromaDB writes until chunks are reviewed and approved.

Target collection (NOT written in pilot): rf_reference_library
"""

import re
import os
import json
import requests
from datetime import datetime
from pathlib import Path

# === CONFIG ===
A4M_DIR = Path(
    "/Users/danielsmith/Library/CloudStorage/GoogleDrive-znahealth@gmail.com/"
    "Shared drives/11. RH Transition/A4M Fertility Course/Transcriptions"
)
OUTPUT_JSON = Path(
    "/Users/danielsmith/Claude - RF 2.0/rf-nashat-clone/data/"
    "a4m_transcript_chunks_full.json"
)
HAIKU_MODEL = "claude-haiku-4-5"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Module number → clean title. Adapted from ingest_reference_library.py MODULE_MAP.
# NOTE: modules 13/14 flipped vs MODULE_MAP to match transcript filename ground truth.
MODULE_TITLES = {
    1:  "Epigenetics & Nutrigenomics: Modernizing Preconception Care",
    2:  "Fertility Assessment — Female",
    3:  "Fertility Assessment — Male",
    4:  "Functional Fertility Assessment",
    5:  "Case Study 1",
    6:  "Fertility Over 40",
    7:  "PCOS and Infertility",
    8:  "Fibroids and Endometriosis",
    9:  "IVF Supportive Care",
    10: "Case Study 2",
    11: "Male Fertility and Diet",
    12: "Recurrent Pregnancy Loss",
    13: "The Reproductive Microbiome",
    14: "Holistic Fertility Enhancement",
}


# === PARSE: speaker blocks (copied from rag_pipeline_v3_llm.py, regex extended) ===
def parse_speaker_blocks(text):
    """Parse lecture text into numbered speaker blocks.
    Handles: 'HH:MM:SS Dr. Name', 'HH:MM:SS SPEAKER_N', 'HH:MM:SS SPK_N'.
    """
    lines = text.split('\n')
    blocks = []
    current = None

    for line in lines:
        speaker_match = re.match(
            r'(\d{2}:\d{2}:\d{2})\s+(Dr\.\s+\w+|SPEAKER_\d+|SPK_\d+)\s*$', line
        )
        if speaker_match:
            if current:
                blocks.append(current)
            current = {
                'idx': len(blocks),
                'timestamp': speaker_match.group(1),
                'speaker': speaker_match.group(2),
                'text': ''
            }
        elif current:
            clean = re.sub(r'\[SCENE CHANGE [^\]]+\]\s*', '', line).strip()
            if clean:
                current['text'] += ' ' + clean

    if current:
        blocks.append(current)

    for b in blocks:
        b['text'] = b['text'].strip()
        b['words'] = len(b['text'].split())
    return blocks


# === HAIKU BOUNDARY DETECTION (adapted from v3, lecture-framed prompt) ===
def get_boundaries_from_llm(blocks, source_id):
    """Send numbered speaker blocks to Haiku, get topic-boundary groupings."""
    total_words = sum(b['words'] for b in blocks)
    if total_words < 300 or len(blocks) < 4:
        return [[b['idx'] for b in blocks]]

    block_text = ""
    for b in blocks:
        preview = b['text'][:150] + ('...' if len(b['text']) > 150 else '')
        block_text += f"[{b['idx']}] {b['speaker']} ({b['words']}w): {preview}\n"

    prompt = f"""You are analyzing a transcript of a medical education lecture on fertility to find natural topic boundaries.

Each numbered block below is one speaker turn. Group these blocks into coherent sections — where one concept, argument, mechanism, or clinical point forms a complete unit.

RULES:
- Each group should be 300-500 words total (sum the word counts shown)
- Never split an example or data point from the claim it supports
- Start a new group when: the lecturer shifts to a new concept, introduces a new study or case, moves from mechanism to clinical application, or you've reached ~500 words
- **Q&A SECTIONS: Each distinct audience question and its answer is its own group** — UNLESS the answer is very short (<150 words total), in which case you may merge closely-related consecutive Q&A exchanges on the same narrow sub-topic. A new audience question is normally a topic boundary.
- Hard ceiling: NO group may exceed 1,100 words. If a topic is naturally longer, split at the most coherent sub-boundary.
- Hard floor: NO group should be under 250 words. If a unit is shorter, merge it with the adjacent group it most relates to.
- Target range: 300-700 words per group. Aim here unless content forces otherwise.
- Return ONLY a JSON array of arrays of block indices

BLOCKS:
{block_text}

Return ONLY valid JSON — an array of arrays of block indices. Example: [[0,1,2],[3,4,5,6],[7,8]]"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": HAIKU_MODEL,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    data = resp.json()
    if 'content' not in data or not data['content']:
        raise RuntimeError(f"Haiku returned no content for {source_id}: {data}")

    text = data['content'][0]['text'].strip()
    text = re.sub(r'^```json\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    groups = json.loads(text)

    if not isinstance(groups, list):
        raise RuntimeError(f"Haiku returned non-list for {source_id}")
    for g in groups:
        if not isinstance(g, list) or not all(isinstance(i, int) for i in g):
            raise RuntimeError(f"Haiku returned malformed group for {source_id}: {g}")
    return groups


# === ASSEMBLE CHUNK FROM BLOCKS (copied from v3, unchanged) ===
def assemble_chunk_from_blocks(blocks, group_indices):
    """Combine speaker blocks by index into a single chunk text."""
    selected = [b for b in blocks if b['idx'] in group_indices]
    if not selected:
        return None
    text = '\n'.join(
        f"[{b['speaker']}] {b['text']}" for b in selected if b['text']
    )
    word_count = sum(b['words'] for b in selected)
    return {
        'text': text,
        'start_time': selected[0]['timestamp'],
        'end_time': selected[-1]['timestamp'],
        'speakers': sorted(set(b['speaker'] for b in selected)),
        'word_count': word_count,
    }


# === A4M-SPECIFIC: filename → (module_num, module_title) ===
def parse_module_from_filename(filename):
    """'Module_1_-Epigenetics_an_Nutrigenomics.txt' → (1, 'Epigenetics & ...')"""
    m = re.match(r'Module[_ ](\d+)', filename)
    if not m:
        return None, None
    num = int(m.group(1))
    return num, MODULE_TITLES.get(num, f"Module {num}")


def attach_metadata(chunk, module_num, module_title, source_file, chunk_index):
    chunk.update({
        "module_number": module_num,
        "module_title": module_title,
        "source_type": "transcript",
        "source_file": source_file,
        "chunk_index": chunk_index,
    })
    return chunk


# === ORCHESTRATION ===
def process_module_pilot(txt_path):
    """One module end-to-end. Returns list of enriched chunks. NO Chroma write."""
    filename = txt_path.name
    module_num, module_title = parse_module_from_filename(filename)
    if module_num is None:
        raise RuntimeError(f"Could not parse module number from: {filename}")

    print(f"  Reading {filename}")
    text = txt_path.read_text(encoding='utf-8')
    print(f"  File size: {len(text):,} chars")

    blocks = parse_speaker_blocks(text)
    print(f"  Parsed {len(blocks)} speaker blocks")
    if not blocks:
        raise RuntimeError(f"No speaker blocks parsed from {filename} — check regex")
    total_words = sum(b['words'] for b in blocks)
    print(f"  Total words: {total_words:,}")

    print(f"  Calling Haiku for boundary detection...")
    groups = get_boundaries_from_llm(blocks, source_id=f"module_{module_num}")
    print(f"  Haiku returned {len(groups)} groups")

    chunks = []
    for i, group_indices in enumerate(groups):
        chunk = assemble_chunk_from_blocks(blocks, group_indices)
        if chunk:
            attach_metadata(chunk, module_num, module_title, filename, i)
            chunks.append(chunk)
    return chunks


def main():
    print(f"{'='*60}")
    print(f"A4M Transcript Ingestion — FULL BATCH (Modules 1-14)")
    print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

    # Discover module files by number prefix — keeps us independent of
    # exact filename spelling after Module_N_.
    module_files = {}
    for p in sorted(A4M_DIR.glob("Module_*.txt")):
        m = re.match(r"Module_(\d+)", p.name)
        if not m:
            continue
        module_files[int(m.group(1))] = p

    missing = [n for n in MODULE_TITLES if n not in module_files]
    if missing:
        raise FileNotFoundError(f"Missing transcript files for modules: {missing}")

    print(f"  Found {len(module_files)} module transcripts")
    print()

    all_chunks = []
    per_module_stats = []

    for module_num in sorted(MODULE_TITLES.keys()):
        path = module_files[module_num]
        print(f"\n{'─'*60}")
        print(f"Module {module_num}: {MODULE_TITLES[module_num]}")
        print(f"{'─'*60}")
        try:
            chunks = process_module_pilot(path)
        except Exception as e:
            print(f"  ❌ FAILED on module {module_num}: {e}")
            raise  # abort-on-failure policy
        all_chunks.extend(chunks)
        wc = [c['word_count'] for c in chunks]
        per_module_stats.append({
            "module": module_num,
            "chunks": len(chunks),
            "mean_words": sum(wc) / len(wc) if wc else 0,
            "min_words": min(wc) if wc else 0,
            "max_words": max(wc) if wc else 0,
        })

    # Aggregate stats
    word_counts = [c['word_count'] for c in all_chunks]
    mean_words = sum(word_counts) / len(word_counts) if word_counts else 0
    print(f"\n{'='*60}")
    print(f"BATCH RESULTS — All Modules")
    print(f"{'='*60}")
    print(f"  Total chunks:      {len(all_chunks)}")
    print(f"  Mean word count:   {mean_words:.0f}")
    print(f"  Min / Max words:   {min(word_counts)} / {max(word_counts)}")
    print(f"  Word count histogram (200w bins):")
    bins = {}
    for w in word_counts:
        b = (w // 200) * 200
        bins[b] = bins.get(b, 0) + 1
    for b in sorted(bins):
        print(f"    {b:>4}-{b+199:<4}: {'#' * bins[b]} ({bins[b]})")

    print(f"\n  Per-module breakdown:")
    print(f"  {'Mod':>4}  {'Chunks':>7}  {'Mean':>6}  {'Min':>5}  {'Max':>5}")
    for s in per_module_stats:
        print(f"  {s['module']:>4}  {s['chunks']:>7}  {s['mean_words']:>6.0f}  {s['min_words']:>5}  {s['max_words']:>5}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(all_chunks, indent=2), encoding='utf-8')
    print(f"\n  Wrote {len(all_chunks)} chunks to: {OUTPUT_JSON}")
    print(f"\n  NO ChromaDB writes performed. Review chunks before approving ingestion.")


if __name__ == "__main__":
    main()
