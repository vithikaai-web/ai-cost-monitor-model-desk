"""
fetch_pricing.py
-----------------
Weekly job: pull the current public model catalog from OpenRouter and merge
fresh price/context numbers into data/models.json.

Design rule: this script is only trusted to update FACTS (price, context
window). It never invents a "tier" or decides what a model is good for —
those are judgment calls that stay yours. Anything it can't confidently
match to an existing row gets added with reviewed=False so it surfaces in
your weekly review instead of silently going live.

Run it locally with:  python scripts/fetch_pricing.py
It's also run automatically by .github/workflows/refresh.yml every Monday.
"""

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

DATA_PATH = Path(__file__).parent.parent / "data" / "models.json"
DIFF_PATH = Path(__file__).parent.parent / "data" / "last_run_diff.md"
OPENROUTER_URL = "https://openrouter.ai/api/v1/models"

# Only sync providers we actually track. OpenRouter's id prefix -> our
# provider label. Add a line here the day you want to start tracking a
# new lab; nothing else in the script needs to change.
PROVIDER_MAP = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
    "google": "Google",
    "deepseek": "DeepSeek",
    "x-ai": "xAI",
    "meta-llama": "Meta",
    "mistralai": "Mistral",
    "moonshotai": "Moonshot AI",
    "z-ai": "Zhipu AI",
    "minimax": "MiniMax",
    "qwen": "Alibaba",
}


def fetch_catalog():
    req = Request(OPENROUTER_URL, headers={"User-Agent": "model-desk-sync/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except URLError as e:
        print(f"FATAL: could not reach OpenRouter ({e}). Leaving models.json untouched.")
        sys.exit(1)
    return payload.get("data", [])


def normalize(name: str) -> str:
    """Loose match key: lowercase, strip spaces/hyphens/dots so
    'GPT-5.5' and 'gpt 5 5' compare equal enough to match."""
    return "".join(ch for ch in name.lower() if ch.isalnum())


def main():
    existing = json.loads(DATA_PATH.read_text())
    models = existing["models"]

    # index existing rows for quick lookup: (provider, normalized name) -> row
    index = {(m["provider"], normalize(m["name"])): m for m in models}

    catalog = fetch_catalog()
    today = date.today().isoformat()

    changed, added, unmatched_review = [], [], []

    for entry in catalog:
        or_id = entry.get("id", "")
        prefix = or_id.split("/")[0] if "/" in or_id else ""
        provider = PROVIDER_MAP.get(prefix)
        if not provider:
            continue  # not a lab we track — skip silently

        pricing = entry.get("pricing", {})
        try:
            input_price = round(float(pricing.get("prompt", 0)) * 1_000_000, 4)
            output_price = round(float(pricing.get("completion", 0)) * 1_000_000, 4)
        except (TypeError, ValueError):
            continue  # malformed pricing block, skip rather than guess

        if input_price == 0 and output_price == 0:
            continue  # free/experimental router entries aren't real pricing signal

        context = entry.get("context_length", 0)
        name = entry.get("name", or_id)
        key = (provider, normalize(name))

        if key in index:
            row = index[key]
            row["orId"] = or_id
            row["lastChecked"] = today
            if row["input"] != input_price or row["output"] != output_price or row["context"] != context:
                changed.append(f"{provider} · {row['name']}: "
                                f"${row['input']}/${row['output']} → ${input_price}/${output_price}, "
                                f"context {row['context']} → {context}")
                row["input"], row["output"], row["context"] = input_price, output_price, context
                row["source"] = "openrouter"
        else:
            new_row = {
                "provider": provider,
                "name": name,
                "tier": "unreviewed",     # <- you assign this by hand
                "date": today,
                "input": input_price,
                "output": output_price,
                "context": context,
                "source": "openrouter",
                "reviewed": False,        # <- flips to True once you've looked at it
                "lastChecked": today,
                "orId": or_id,
            }
            models.append(new_row)
            added.append(f"{provider} · {name}: ${input_price}/${output_price}, context {context}")
            unmatched_review.append(new_row)

    existing["generatedAt"] = today
    DATA_PATH.write_text(json.dumps(existing, indent=2) + "\n")

    # Human-readable diff for the commit + your weekly review
    lines = [f"# Pricing sync — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", ""]
    lines.append(f"Checked {len(catalog)} catalog entries, tracking {len(PROVIDER_MAP)} providers.")
    lines.append("")
    if changed:
        lines.append(f"## Price/context changes ({len(changed)})")
        lines += [f"- {c}" for c in changed]
        lines.append("")
    if added:
        lines.append(f"## New models added — need your review ({len(added)})")
        lines += [f"- {a}" for a in added]
        lines.append("")
    if not changed and not added:
        lines.append("No changes detected. Nothing to review this week.")
    DIFF_PATH.write_text("\n".join(lines) + "\n")

    print("\n".join(lines))
    if unmatched_review:
        print(f"\n⚠ {len(unmatched_review)} new model(s) added with tier='unreviewed' — "
              f"open data/models.json and assign a real tier + decide which use-case "
              f"cards they belong in.")


if __name__ == "__main__":
    main()
