"""
Session 25 — BACKLOG #20 A/B validation.

Live /chat pipeline comparison: baseline (citation_instructions stripped) vs
treatment (YAML as-shipped). Tests both agents across queries targeting full
metadata (locator + link) and queries that may land on degraded-metadata
chunks (source name only).

Method: replicates the rag_server/app.py /chat pipeline in-process (same
retrieval, same prompt assembly, same Claude call) — avoids running the
live Flask server. For each (agent, query, condition), we:
  1. Load agent config fresh via ConfigLoader
  2. For condition=baseline, override behavior.citation_instructions to ""
  3. Retrieve chunks once (identical across A/B — retrieval is deterministic
     given the same query embedding and collection state)
  4. Format context via the canonical renderer with the agent's render config
  5. Assemble system prompt via app.assemble_system_prompt()
  6. Call Claude API directly with the same temperature/max_tokens as YAML
  7. Capture response + token counts

Output: side-by-side A/B for visual review + structured summary dict printed
at the end.

Read-only: no Chroma writes, no file writes (unless --dump-json is passed).
No git ops. No .env reads (inherits from shell/load_dotenv).

Spend estimate: 8 Sonnet calls × ~$0.02-0.04 = ~$0.15-0.30 total.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Repo root on path so we can import rag_server/shared/config
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(_REPO_ROOT / ".env")

import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import requests

from shared.config_loader import ConfigLoader
from config.schema import AgentConfig, Mode
from rag_server.display import format_context as _format_context_v2
from rag_server.app import assemble_system_prompt  # reuse the real assembler

# =============================================================================
# CONFIG
# =============================================================================

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
CHROMA_DB_PATH = os.environ.get(
    "CHROMA_DB_PATH",
    str(_REPO_ROOT.parent / "chroma_db"),
)

# Test matrix. Two per agent; first targets full-metadata source (locator +
# link present), second targets a query where the retrieval may land on
# mixed metadata quality (including potentially legacy A4M with no locator
# or link).
CASES = [
    # (agent_yaml, label, query)
    ("nashat_sales",    "S1", "What should I know about egg quality and age?"),
    ("nashat_sales",    "S2", "Any advice on reducing sugar for fertility?"),
    ("nashat_coaching", "C1", "How does stress affect fertility outcomes?"),
    ("nashat_coaching", "C2", "What supplements support ovulation?"),
]


# =============================================================================
# PIPELINE (replicates rag_server/app.py)
# =============================================================================

def _load_config(agent_name: str) -> AgentConfig:
    path = _REPO_ROOT / "config" / f"{agent_name}.yaml"
    return ConfigLoader(path).config


def _strip_citations(cfg: AgentConfig) -> AgentConfig:
    """Return a copy of cfg with citation_instructions blanked."""
    new_cfg = copy.deepcopy(cfg)
    new_cfg.behavior.citation_instructions = ""
    return new_cfg


def _get_collections(cfg: AgentConfig) -> dict[str, Any]:
    """Open Chroma collections listed in cfg.knowledge.knowledge_collections."""
    openai_ef = OpenAIEmbeddingFunction(
        api_key=OPENAI_API_KEY,
        model_name=cfg.knowledge.retrieval_config.embedding_model,
    )
    client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    out = {}
    for name in cfg.knowledge.knowledge_collections:
        out[name] = client.get_collection(name, embedding_function=openai_ef)
    return out


def _retrieve(
    question: str, mode: Mode, collections: dict[str, Any]
) -> list[dict]:
    """Same shape as rag_server.app.retrieve_for_mode."""
    n_map = {
        "rf_coaching_transcripts": mode.coaching_n,
        "rf_reference_library":    mode.reference_n,
        "rf_published_content":    mode.published_n,
    }
    chunks: list[dict] = []
    for coll_name in mode.collections:
        n = n_map.get(coll_name, 0)
        if n == 0:
            continue
        coll = collections.get(coll_name)
        if coll is None:
            continue
        results = coll.query(query_texts=[question], n_results=n)
        for i in range(len(results["documents"][0])):
            chunks.append({
                "text":     results["documents"][0][i],
                "metadata": results["metadatas"][0][i] or {},
                "distance": results["distances"][0][i],
                "source":   coll_name,
            })
    return chunks


def _call_claude(
    system_prompt: str, user_content: str,
    model: str, max_tokens: int, temperature: float,
) -> dict:
    """Direct Anthropic Messages API call. Returns {text, input_tokens,
    output_tokens, stop_reason} or {error}."""
    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not set"}
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "Content-Type":      "application/json",
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model":       model,
                "max_tokens":  max_tokens,
                "temperature": temperature,
                "system":      system_prompt,
                "messages":    [{"role": "user", "content": user_content}],
            },
            timeout=90,
        )
        data = resp.json()
        if "content" in data and data["content"]:
            usage = data.get("usage", {})
            return {
                "text":          data["content"][0]["text"],
                "input_tokens":  usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "stop_reason":   data.get("stop_reason"),
            }
        if "error" in data:
            return {"error": data["error"].get("message", str(data["error"]))}
        return {"error": f"unexpected response: {json.dumps(data)[:300]}"}
    except Exception as e:
        return {"error": f"request failure: {e}"}


def _sonnet_cost(in_tok: int, out_tok: int) -> float:
    """Sonnet 4.x pricing: $3/M input, $15/M output."""
    return (in_tok / 1_000_000) * 3.0 + (out_tok / 1_000_000) * 15.0


# =============================================================================
# RUNNER
# =============================================================================

def _chunk_meta_summary(chunks: list[dict]) -> str:
    """One-line summary of retrieved chunk metadata for audit trail."""
    parts = []
    for i, ch in enumerate(chunks):
        m = ch["metadata"]
        src = (m.get("source_file_name")
               or (f"A4M M{m.get('module_number')}"
                   if m.get("module_number") else None)
               or ch.get("source", "?"))
        loc  = m.get("display_locator") or ""
        link = "L" if m.get("source_web_view_link") else "-"
        parts.append(f"[{i}] {src} {loc} {link}")
    return " | ".join(parts)


def run_case(agent_name: str, label: str, query: str) -> dict:
    print(f"\n{'=' * 78}")
    print(f"  {label} — {agent_name} — {query!r}")
    print('=' * 78)

    cfg_treatment = _load_config(agent_name)
    cfg_baseline  = _strip_citations(cfg_treatment)

    mode_name = cfg_treatment.behavior.default_mode
    mode      = cfg_treatment.behavior.modes[mode_name]

    # Retrieval is identical across A/B — same query, same collection state.
    collections = _get_collections(cfg_treatment)
    chunks      = _retrieve(query, mode, collections)
    context     = _format_context_v2(
        chunks,
        render_configs=cfg_treatment.knowledge.render,
    )

    meta_summary = _chunk_meta_summary(chunks)
    print(f"  mode={mode_name}  chunks={len(chunks)}")
    print(f"  retrieved: {meta_summary}")

    sys_prompt_treatment = assemble_system_prompt(cfg_treatment, mode)
    sys_prompt_baseline  = assemble_system_prompt(cfg_baseline,  mode)
    user_content = f"{context}\n\nUSER QUESTION:\n{query}" if context else query

    verify_citation_block = "CITATION GUIDANCE:" in sys_prompt_treatment
    verify_stripped       = "CITATION GUIDANCE:" not in sys_prompt_baseline
    print(f"  prompts ok: treatment has CITATION GUIDANCE={verify_citation_block}, "
          f"baseline stripped={verify_stripped}")

    model     = cfg_treatment.behavior.model_name
    max_tok   = cfg_treatment.behavior.max_tokens
    temp      = cfg_treatment.behavior.temperature

    print(f"\n--- BASELINE (no citation_instructions) ---")
    t0 = time.time()
    base_out = _call_claude(
        sys_prompt_baseline, user_content, model, max_tok, temp,
    )
    t_base = time.time() - t0
    if "error" in base_out:
        print(f"  ERROR: {base_out['error']}")
    else:
        cost_b = _sonnet_cost(base_out["input_tokens"], base_out["output_tokens"])
        print(f"  [{base_out['input_tokens']} in / {base_out['output_tokens']} out / "
              f"${cost_b:.4f} / {t_base:.1f}s]")
        print()
        print(base_out["text"])

    print(f"\n--- TREATMENT (YAML citation_instructions) ---")
    t0 = time.time()
    treat_out = _call_claude(
        sys_prompt_treatment, user_content, model, max_tok, temp,
    )
    t_treat = time.time() - t0
    if "error" in treat_out:
        print(f"  ERROR: {treat_out['error']}")
    else:
        cost_t = _sonnet_cost(treat_out["input_tokens"], treat_out["output_tokens"])
        print(f"  [{treat_out['input_tokens']} in / {treat_out['output_tokens']} out / "
              f"${cost_t:.4f} / {t_treat:.1f}s]")
        print()
        print(treat_out["text"])

    return {
        "label":        label,
        "agent":        agent_name,
        "query":        query,
        "mode":         mode_name,
        "chunk_count":  len(chunks),
        "meta_summary": meta_summary,
        "baseline":     base_out,
        "treatment":    treat_out,
    }


def main():
    if not ANTHROPIC_API_KEY:
        print("FATAL: ANTHROPIC_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)
    if not OPENAI_API_KEY:
        print("FATAL: OPENAI_API_KEY not set in environment.", file=sys.stderr)
        sys.exit(1)

    print("=" * 78)
    print("  S25 — BACKLOG #20 A/B validation (live)")
    print("=" * 78)
    print(f"  cases: {len(CASES)}  ×  2 conditions  =  {len(CASES) * 2} Sonnet calls")
    print(f"  model: claude-sonnet-4-6, temp: YAML-configured (0.4), max_tok: 1500")

    results = []
    total_in = 0
    total_out = 0
    for agent_name, label, query in CASES:
        r = run_case(agent_name, label, query)
        results.append(r)
        for cond in ("baseline", "treatment"):
            if "input_tokens" in r[cond]:
                total_in  += r[cond]["input_tokens"]
                total_out += r[cond]["output_tokens"]

    total_cost = _sonnet_cost(total_in, total_out)
    print(f"\n{'=' * 78}")
    print(f"  SUMMARY")
    print('=' * 78)
    print(f"  cases run:     {len(results)}")
    print(f"  total tokens:  {total_in} in / {total_out} out")
    print(f"  total cost:    ${total_cost:.4f}")

    if "--dump-json" in sys.argv:
        out_path = _REPO_ROOT / "data" / "s25_citation_ab_results.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, default=str))
        print(f"  dumped to:     {out_path}")


if __name__ == "__main__":
    main()
