#!/usr/bin/env python3
"""Live-calibration test for ingester.classify — live Haiku calls.

NOT in the regression suite (per s25 flight rule — live-API scripts live
in scripts/ but NOT in Step 0 regression, because they cost money and
are non-deterministic across sessions).

Runs 8 known-labeled samples through the classifier (4 marketing + 4
operational) and reports accuracy. Cost ~$0.005 first run; $0 on cache hits.

Usage:
  ./venv/bin/python scripts/test_classify_live_s28.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from ingester.classify import classify  # noqa: E402


CASES = [
    # ---- Known MARKETING / EDUCATIONAL ----
    (
        "MARKETING",
        "The Sunshine Vitamin: Enhancing Fertility with Vitamin D",
        "Did you know that Vitamin D is one of the most overlooked nutrients when it comes to fertility? Low Vitamin D levels have been associated with ovulatory dysfunction, PCOS, endometriosis, and reduced implantation rates. In this blog, we'll cover the science, the optimal range, and how to test your levels.",
    ),
    (
        "MARKETING",
        "Welcome to my Fertility Kickstart email series",
        "Over the next 5 days, I'll walk you through the 3 root causes of unexplained infertility I see most often in my practice — and what you can do about each one starting today. Let's start with the gut-fertility connection.",
    ),
    (
        "MARKETING",
        "Is sugar sabotaging your fertility?",
        "Most couples trying to conceive don't realize that sugar does more than affect weight — it disrupts hormone balance, increases inflammation, and affects egg and sperm quality. Here's what the research shows and 5 simple swaps you can make this week.",
    ),
    (
        "MARKETING",
        "Your free 7-day hormone reset guide",
        "Thanks for downloading our 7-Day Hormone Reset! Inside you'll find daily nutrition protocols, morning and evening routines, and the top 3 supplements our clients use to feel human again within a week. Let's get started.",
    ),

    # ---- Known OPERATIONAL / TRANSACTIONAL ----
    (
        "OPERATIONAL",
        "Your unsubscription confirmation",
        "This is to confirm that you have been unsubscribed from our email list. If this was a mistake, you can re-subscribe using the link below. Thank you.",
    ),
    (
        "OPERATIONAL",
        "Reminder: Your FKSP kickoff call is tomorrow at 2pm EST",
        "Hi Sarah, just a quick reminder that your FKSP kickoff call with Dr. Nashat is tomorrow, Wednesday, at 2pm Eastern. The Zoom link is below. Please have your intake form and lab results ready.",
    ),
    (
        "OPERATIONAL",
        "Payment received — invoice #4827",
        "Thank you for your payment of $497.00. This confirms enrollment in The Fertility Formula. Your welcome email with login credentials will arrive within 24 hours. View invoice PDF attached.",
    ),
    (
        "OPERATIONAL",
        "Password reset requested",
        "We received a request to reset the password for your account. If you did not make this request, you can ignore this email. Otherwise, click the link below to set a new password. The link expires in 1 hour.",
    ),
]


def main() -> int:
    print("Running 8 calibration cases through ingester.classify...")
    print()
    correct = 0
    total_cost = 0.0
    for expected, subject, body in CASES:
        result = classify(subject=subject, body_preview=body)
        match = "✓" if result.verdict == expected else "✗"
        if result.verdict == expected:
            correct += 1
        cached_marker = " (cached)" if result.cached else ""
        print(f"  {match} expected={expected:<12} got={result.verdict:<12}"
              f"  cost=${result.cost_usd:.6f}{cached_marker}")
        print(f"      subj: {subject[:70]}")
        total_cost += result.cost_usd
    print()
    print(f"  {correct}/{len(CASES)} passing, {len(CASES) - correct} failing")
    print(f"  total cost: ${total_cost:.6f}")
    return 0 if correct == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())
