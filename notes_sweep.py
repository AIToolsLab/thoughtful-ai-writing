#!/usr/bin/env python3
"""How much should a writer put in the Thinking Box?

Scores one finished text under several versions of the notes, from none to very
detailed, using the class vLLM server. For each version it reports:

  note_bits   information in the plan itself, scored where the page puts it:
              inside the request "Help me write a short piece. Here is what I want to say: ..."
  text_bits   information left in the text once the notes are in the prompt
  saved       text bits without notes minus text bits with these notes
  used        saved / note_bits: how much of the notes' information ended up in
              the text (near 100% = every note was used; low = notes the text
              never needed)
  combined    note_bits + text_bits: total information the writer supplied

The chat framing matches bit_meter.html (see qwen_chat.py), so the numbers line up
with the page's "Measure what the plan saved" button.

Notes file format: versions separated by a line containing only ---.
Put them in order from least to most detail; an empty version is added
automatically as the no-notes baseline.

Usage:
  python notes_sweep.py essay.txt notes_versions.txt
  python notes_sweep.py essay.txt notes_versions.txt --out results/notes
"""
import argparse
import csv
import os

import qwen_chat as qc


def score_version(base, model, text, notes):
    """Bits of the plan (inside the request) and of the text (as the reply), framed like the page."""
    notes = notes.strip()
    text_bits = qc.total_bits(qc.score_span(base, model, qc.chat_prefix(base, model, qc.history_for(notes)), text))
    note_bits = qc.total_bits(qc.score_span(base, model, qc.turn_prefix(base, model, []) + qc.REQUEST_HEAD, notes)) if notes else 0.0
    return note_bits, text_bits


def plot(rows, baseline, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping the chart")
        return
    xs = [r["note_words"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.6, 4.4), dpi=150)
    ax.axhline(baseline, color="#98a1b1", linestyle="--", linewidth=1)
    ax.text(xs[-1], baseline, " text alone, no notes", va="bottom", ha="right", fontsize=8, color="#5a6476")
    ax.plot(xs, [r["text_bits"] for r in rows], marker="o", color="#b07510", label="Bits left in the text")
    ax.plot(xs, [r["combined"] for r in rows], marker="o", color="#6a4bc4", label="Notes + text (all you supplied)")
    for r in rows[1:]:
        ax.annotate(f'{round(100 * r["used"])}% used', (r["note_words"], r["text_bits"]),
                    textcoords="offset points", xytext=(0, -14), ha="center", fontsize=7, color="#5a6476")
    ax.set_xlabel("Words in the Thinking Box")
    ax.set_ylabel("Bits")
    ax.set_ylim(bottom=0)
    ax.grid(True, color="#d3d9e3", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, fontsize=8)
    ax.set_title("What the Thinking Box buys", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"wrote {out_png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", help="the finished text (plain .txt)")
    ap.add_argument("notes", help="notes versions separated by lines of ---")
    ap.add_argument("--vllm", default=qc.DEFAULT_SERVER)
    ap.add_argument("--model", default=None)
    ap.add_argument("--out", default="results/notes")
    a = ap.parse_args()

    text = open(a.text, encoding="utf-8").read().strip()
    raw = open(a.notes, encoding="utf-8").read()
    versions = [""] + [" ".join(v.split()) for v in raw.split("\n---") if v.strip(" -\n")]
    model = a.model or qc.pick_model(a.vllm)
    print(f"scoring {len(versions)} versions with {model}")

    rows, baseline = [], None
    for i, notes in enumerate(versions):
        nb, tb = score_version(a.vllm, model, text, notes)
        if baseline is None:
            baseline = tb
        saved = baseline - tb
        rows.append({
            "version": i, "note_words": len(notes.split()), "note_bits": round(nb, 2), "text_bits": round(tb, 2),
            "saved": round(saved, 2), "used": round(saved / nb, 4) if nb else 0.0, "combined": round(nb + tb, 2),
            "notes": notes,
        })

    prev = None
    print(f"\n{'ver':>3} {'words':>5} {'note bits':>9} {'text bits':>9} {'saved':>7} {'used':>6} {'marginal':>8}")
    for r in rows:
        marg = ""
        if prev is not None and r["note_bits"] > prev["note_bits"]:
            marg = f'{(r["saved"] - prev["saved"]) / (r["note_bits"] - prev["note_bits"]):.0%}'
        r["marginal_used"] = marg
        print(f'{r["version"]:>3} {r["note_words"]:>5} {r["note_bits"]:>9.1f} {r["text_bits"]:>9.1f} '
              f'{r["saved"]:>7.1f} {r["used"]:>6.0%} {marg:>8}')
        prev = r
    print("\nmarginal = extra bits saved per extra bit of notes, compared with the previous version.")
    print("When it drops sharply, the extra detail isn't paying for itself.")

    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "notes_sweep.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    plot(rows, baseline, os.path.join(a.out, "notes_sweep.png"))


if __name__ == "__main__":
    main()
