#!/usr/bin/env python3
"""Score Bit Meter session logs and draw the speed-vs-control chart.

Each session log (exported from bit_meter.html) records every word, who put it
there (typed / chose / accepted / generated) and the bits the page computed
live. For the study, every condition must be measured by the same model, so by
default this script rescores the final text of each session with the writing
engine and recomputes the bits per word.

Scoring uses the same chat framing as the page (see qwen_chat.py): the plan is the
user's request and the text is the assistant's reply.

How the human bits are recomputed:
  typed      -> its full surprisal under the rescoring model
  chose      -> the claim from the log (choice bits, plus prefix bits if letters
                were typed), capped at the rescored bits of that option
  accepted   -> the claim from the log (0, or prefix bits if letters were typed)
  generated  -> 0
  plan       -> surprisal of the plan inside the request (plan bits)
  chat       -> the writer's chat messages count as human bits, the AI's replies
                as AI bits (sessions.csv: chat_writer_bits, chat_assistant_bits,
                control_with_chat)

Usage:
  python score_sessions.py logs/*.json            # rescore with the class Qwen server
  python score_sessions.py logs/*.json --no-rescore        # use the logged bits

Outputs (in --out, default ./results):
  sessions.csv   one row per session: condition, speed and control metrics
  units.csv      one row per word: text, source, model bits, human bits
  tradeoff.png   speed (x) vs human share of bits (y), one point per session
"""
import argparse
import csv
import json
import os
import sys

import qwen_chat as qc


def rescore(log, base, model):
    """Rescore a session's final text in the same chat framing the page uses."""
    head = log.get("requestHead") or qc.REQUEST_HEAD
    base_request = log.get("baseRequest") or qc.BASE_REQUEST
    chat = log.get("chat") or []
    messages = log.get("messages") or qc.history_for(log.get("notes"), chat, head=head, base_request=base_request)
    text = "".join(u["text"] for u in log["units"])
    # One pass over chat + plan + text, split by who supplied each part (see qwen_chat.split_bits).
    split, toks = qc.split_bits(base, model, messages, log.get("notes"), text, head=head)
    log["split"] = split
    starts, pos = [], 0
    for u in log["units"]:
        starts.append(pos); pos += len(u["text"]); u["bits"] = 0.0
    j = 0
    for at, b in toks:
        while j + 1 < len(starts) and starts[j + 1] <= at:
            j += 1
        log["units"][j]["bits"] += b
    # Human bits: typed words get all their bits; chosen / accepted / generated text keeps the claim
    # recorded when it was added, capped at the bits of everything added in that step.
    groups = {}
    for u in log["units"]:
        if u["src"] == "typed":
            u["hbits"] = u["bits"]
        elif u["src"] == "generated":
            u["hbits"] = 0.0
        elif "group" in u:
            groups.setdefault(u["group"], []).append(u)
    for g in groups.values():
        total = sum(u["bits"] for u in g)
        for i, u in enumerate(g):
            u["hbits"] = min(g[0].get("claim", 0.0), total) if i == 0 else 0.0
    log["noteBits"] = split["plan"]


def summarize(log, path):
    units = [u for u in log["units"] if u.get("bits") is not None]
    total = sum(u["bits"] for u in units)
    human = sum(u["hbits"] or 0 for u in units)
    notes = log.get("noteBits") or 0.0
    s = log.get("summary", {})
    keys = s.get("keystrokes", 0)
    secs = s.get("seconds", 0)
    words = s.get("words", 0)
    by = {k: sum(u["hbits"] or 0 for u in units if u["src"] == k) for k in ("typed", "chose", "accepted", "generated")}
    sp = log.get("split") or {}
    chat_w, chat_a = sp.get("writer", 0.0), sp.get("assistant", 0.0)
    all_h, all_b = human + notes + chat_w, total + notes + chat_w + chat_a
    return {
        "file": os.path.basename(path),
        "condition": log.get("condition"),
        "model": log.get("model"),
        "example": log.get("example", False),
        "words": words,
        "seconds": secs,
        "wpm": round(words / (secs / 60), 2) if secs > 0 else "",
        "keystrokes": keys,
        "keystrokes_per_word": round(keys / words, 3) if words else "",
        "total_bits": round(total, 3),
        "human_bits": round(human, 3),
        "steering_bits": round(notes, 3),
        "control": round((human + notes) / (total + notes), 4) if total + notes else "",
        "control_no_steering": round(human / total, 4) if total else "",
        "chat_writer_bits": round(chat_w, 3),
        "chat_assistant_bits": round(chat_a, 3),
        "chat_turns": len(sp.get("turns", [])),
        "control_with_chat": round(all_h / all_b, 4) if all_b else "",
        "human_bits_per_keystroke": round(human / keys, 4) if keys else "",
        "choices": sum(1 for u in units if u["src"] == "chose"),
        "bits_typed": round(by["typed"], 3),
        "bits_chosen": round(by["chose"], 3),
        "bits_accepted_prefix": round(by["accepted"], 3),
    }


def plot(rows, out_png):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed; skipping tradeoff.png", file=sys.stderr)
        return
    colors = {"plain": "#2747d0", "assist": "#0a8571", "generate": "#c03a54"}
    names = {"plain": "Plain typing", "assist": "Our tool", "generate": "Full generation"}
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=150)
    for cond in ("plain", "generate", "assist"):
        pts = [r for r in rows if r["condition"] == cond and r["wpm"] != "" and r["control"] != ""]
        if not pts:
            continue
        xs = [r["wpm"] for r in pts]
        ys = [100 * r["control"] for r in pts]
        ax.scatter(xs, ys, s=36, color=colors[cond], alpha=0.75, label=names[cond], edgecolors="none")
        ax.scatter([sum(xs) / len(xs)], [sum(ys) / len(ys)], s=140, color=colors[cond], marker="D", edgecolors="white", linewidths=1.2)
    ax.set_xlabel("Words per minute")
    ax.set_ylabel("Human share of bits (%)")
    ax.set_ylim(0, 105)
    ax.set_xlim(left=0)
    ax.grid(True, color="#d3d9e3", linewidth=0.6)
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False, loc="lower left")
    ax.set_title("Speed vs. control (diamonds = condition means)", fontsize=10, loc="left")
    fig.tight_layout()
    fig.savefig(out_png)
    print(f"wrote {out_png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("logs", nargs="+", help="session JSON files exported from the Bit Meter")
    ap.add_argument("--vllm", default=qc.DEFAULT_SERVER, help="writing engine address (flag name kept for old commands)")
    ap.add_argument("--model", default=None, help="model name (default: first model the server lists)")
    ap.add_argument("--no-rescore", action="store_true", help="use the bits recorded in the logs")
    ap.add_argument("--include-examples", action="store_true", help="keep the page's built-in example session")
    ap.add_argument("--out", default="results")
    a = ap.parse_args()

    model = None
    if not a.no_rescore:
        model = a.model or qc.pick_model(a.vllm)
        print(f"rescoring with {model} at {a.vllm}")

    os.makedirs(a.out, exist_ok=True)
    rows, unit_rows = [], []
    for path in a.logs:
        with open(path) as f:
            log = json.load(f)
        if log.get("example") and not a.include_examples:
            print(f"skipping example session {path}")
            continue
        if model:
            rescore(log, a.vllm, model)
        rows.append(summarize(log, path))
        for i, u in enumerate(log["units"]):
            unit_rows.append({
                "file": os.path.basename(path), "condition": log.get("condition"), "i": i,
                "text": u["text"], "src": u["src"], "bits": u.get("bits"), "hbits": u.get("hbits"),
                "keys": u.get("keys"), "H": u.get("H", ""), "choice": u.get("choice", ""),
            })

    if not rows:
        sys.exit("no sessions to score")
    with open(os.path.join(a.out, "sessions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)
    with open(os.path.join(a.out, "units.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(unit_rows[0].keys()))
        w.writeheader(); w.writerows(unit_rows)
    print(f"wrote {len(rows)} sessions and {len(unit_rows)} words to {a.out}/")

    by = {}
    for r in rows:
        by.setdefault(r["condition"], []).append(r)
    print(f"\n{'condition':<10} {'n':>3} {'wpm':>7} {'control':>8} {'bits/key':>9}")
    for cond, rs in by.items():
        def mean(k):
            v = [r[k] for r in rs if r[k] != ""]
            return sum(v) / len(v) if v else float("nan")
        print(f"{cond:<10} {len(rs):>3} {mean('wpm'):>7.1f} {100 * mean('control'):>7.1f}% {mean('human_bits_per_keystroke'):>9.2f}")

    plot(rows, os.path.join(a.out, "tradeoff.png"))


if __name__ == "__main__":
    main()
