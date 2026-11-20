"""Shared helpers for scoring text with Prof. Arnold's writing engine, exactly like bit_meter.html.

The engine (https://llm.thoughtful-ai.com, see writing-prototypes/engine/MIGRATING.md) replaced the
vLLM server in Nov 2026. We use two of its routes:
  POST /v1/template  {messages, add_generation_prompt, enable_thinking} -> {prompt}
  POST /v1/score     {session, prompt, text} -> {tokens: [{text, logprob, ...}]}

The page sends a chat:
  ...earlier chat turns (the writer's messages and the AI's replies)...
  user:       "Help me write a short piece. Here is what I want to say:\n\n<plan>"
              (or just "Help me write a short piece." with no plan)
  assistant:  the writer's text
"""
import json
import math
import urllib.request

LN2 = math.log(2)
DEFAULT_SERVER = "https://llm.thoughtful-ai.com"
BASE_REQUEST = "Help me write a short piece."
REQUEST_HEAD = f"{BASE_REQUEST} Here is what I want to say:\n\n"
PLACEHOLDER = "XYZZYPLACEHOLDER"
SESSION = "score-sessions"  # the engine keeps a cache per session; one for these scripts


def post(base, path, body, timeout=180):
    req = urllib.request.Request(base.rstrip("/") + path, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def pick_model(base):
    with urllib.request.urlopen(base.rstrip("/") + "/v1/models", timeout=30) as r:
        ids = [m["id"] for m in json.load(r)["data"]]
    return next((i for i in ids if "3.8" in i), ids[0])


def request_text(notes, head=REQUEST_HEAD, base_request=BASE_REQUEST):
    notes = (notes or "").strip()
    return head + notes if notes else base_request


def history_for(notes, chat=None, **kw):
    return list(chat or []) + [{"role": "user", "content": request_text(notes, **kw)}]


_cache = {}


def prefix(base, history, role="assistant"):
    """The chat-templated prompt up to where a new message from `role` starts, after `history`."""
    key = (base, role, json.dumps(history))
    if key not in _cache:
        if role == "assistant":
            _cache[key] = post(base, "/v1/template", {"messages": history, "add_generation_prompt": True,
                                                      "enable_thinking": False})["prompt"]
        else:
            p = post(base, "/v1/template", {"messages": list(history) + [{"role": role, "content": PLACEHOLDER}],
                                            "add_generation_prompt": False, "enable_thinking": False})["prompt"]
            _cache[key] = p[:p.rindex(PLACEHOLDER)]
    return _cache[key]


def chat_prefix(base, model, messages):
    """Kept for older code: the prompt for `messages`, ending with the assistant's turn."""
    return prefix(base, messages, "assistant")


def score_span(base, model, prompt, text):
    """Bits of each token of `text` given `prompt`, as [(offset_in_text, bits)].

    Each token is credited to its first non-space character, so " Car" belongs to "C".
    """
    if not text:
        return []
    toks = post(base, "/v1/score", {"session": SESSION, "prompt": prompt, "text": text})["tokens"]
    out, pos = [], 0
    for t in toks:
        lead = len(t["text"]) - len(t["text"].lstrip())
        out.append((pos + lead if lead < len(t["text"]) else pos, -t["logprob"] / LN2))
        pos += len(t["text"])
    return out


def total_bits(toks):
    return sum(b for _, b in toks)


def split_bits(base, model, messages, notes, draft, head=REQUEST_HEAD):
    """Score chat turns, plan and draft, and split the bits by who supplied them (same as the page).

    `messages` is the chat turns followed by the request message (as the page logs them).
    Each part is scored given everything before it. Returns (split, draft_tokens):
      split = {"writer", "assistant", "plan", "turns": [{"role", "bits"}]}
        writer     the writer's chat messages (human)
        assistant  the AI's chat replies (AI)
        plan       the plan inside the request (human)
      draft_tokens = [(offset_in_draft, bits)], to credit word by word.
    Chat-template markup and the fixed request wording aren't scored.
    """
    turns = list(messages[:-1])
    split = {"writer": 0.0, "assistant": 0.0, "plan": 0.0, "turns": []}
    for i, m in enumerate(turns):
        b = total_bits(score_span(base, model, prefix(base, turns[:i], m["role"]), m["content"]))
        split["turns"].append({"role": m["role"], "bits": b})
        split["writer" if m["role"] == "user" else "assistant"] += b
    notes = (notes or "").strip()
    if notes:
        split["plan"] = total_bits(score_span(base, model, prefix(base, turns, "user") + head, notes))
    draft_toks = score_span(base, model, prefix(base, messages, "assistant"), draft)
    return split, draft_toks
