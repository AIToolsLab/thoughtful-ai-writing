"""Shared helpers for scoring text with the class vLLM server, framed exactly like bit_meter.html.

The page (following Prof. Arnold's writing-prototypes, Nov 2026) sends a chat:
  user:       "Help me write a short piece. Here is what I want to say:\n\n<plan>"
              (or just "Help me write a short piece." with no plan)
  assistant:  the writer's text
The chat prefix is rendered by the server's own template (/tokenize, then /detokenize) with
thinking turned off, and the text is appended to it, so the template can't trim whitespace.
"""
import json
import math
import urllib.request

LN2 = math.log(2)
DEFAULT_SERVER = "https://vllm.thoughtful-ai.com"
BASE_REQUEST = "Help me write a short piece."
REQUEST_HEAD = f"{BASE_REQUEST} Here is what I want to say:\n\n"
CHAT_TEMPLATE_KWARGS = {"enable_thinking": False}
PLACEHOLDER = "XYZZYPLACEHOLDER"


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


def chat_prefix(base, model, messages):
    """The rendered prompt for `messages`, ending with the assistant generation prompt."""
    key = ("a", base, model, json.dumps(messages))
    if key not in _cache:
        toks = post(base, "/tokenize", {"model": model, "messages": messages, "add_generation_prompt": True,
                                        "chat_template_kwargs": CHAT_TEMPLATE_KWARGS})["tokens"]
        _cache[key] = post(base, "/detokenize", {"model": model, "tokens": toks})["prompt"]
    return _cache[key]


def turn_prefix(base, model, history, role="user"):
    """The rendered prompt up to the start of a new message from `role` after `history`."""
    key = ("t", base, model, role, json.dumps(history))
    if key not in _cache:
        toks = post(base, "/tokenize", {"model": model, "messages": list(history) + [{"role": role, "content": PLACEHOLDER}],
                                        "add_generation_prompt": False, "chat_template_kwargs": CHAT_TEMPLATE_KWARGS})["tokens"]
        prompt = post(base, "/detokenize", {"model": model, "tokens": toks})["prompt"]
        _cache[key] = prompt[:prompt.rindex(PLACEHOLDER)]
    return _cache[key]


def score_span(base, model, prefix, span):
    """Bits of each token of `span` (which ends the prompt), as [(offset_in_span, bits)].

    Each token is credited to its first non-space character, so " Car" belongs to "C".
    """
    if not span:
        return []
    ch = post(base, "/v1/completions", {"model": model, "prompt": prefix + span, "max_tokens": 1, "temperature": 0,
                                        "prompt_logprobs": 1, "return_token_ids": True})["choices"][0]
    plp, ids = ch["prompt_logprobs"], ch["prompt_token_ids"]
    out, end = [], len(span)
    for i in range(len(ids) - 1, -1, -1):
        if end <= 0:
            break
        e = plp[i] and plp[i].get(str(ids[i]))
        if not e:
            break
        t = e.get("decoded_token") or ""
        start = end - len(t)
        lead = len(t) - len(t.lstrip())
        at = start + lead if lead < len(t) else start
        if at >= 0:
            out.append((at, -e["logprob"] / LN2))
        end = start
    return out[::-1]


def total_bits(toks):
    return sum(b for _, b in toks)


def split_bits(base, model, messages, notes, draft):
    """Score chat + plan + draft in one pass and split the bits by who supplied them.

    `messages` is the chat turns followed by the request message (as the page logs them).
    Returns (split, draft_tokens):
      split = {"writer", "assistant", "plan", "frame", "turns": [{"role", "bits"}], "located"}
        writer     the writer's chat messages (human)
        assistant  the AI's chat replies (AI)
        plan       the plan inside the request (human)
        frame      chat-template markup and the fixed request wording (not counted)
      draft_tokens = [(offset_in_draft, bits)], to credit word by word as before.
    Same rules as bit_meter.html: each token belongs to its first non-space character.
    """
    prefix = chat_prefix(base, model, messages)
    toks = score_span(base, model, "", prefix + draft)
    segs, cur, located = [], 0, True
    notes = (notes or "").strip()

    def find(text, kind, turn):
        nonlocal cur, located
        t = (text or "").strip()
        if not t:
            return
        i = prefix.find(t, cur)
        if i < 0:
            located = False
            return
        segs.append((i, i + len(t), kind, turn))
        cur = i + len(t)

    for k, m in enumerate(messages):
        if k == len(messages) - 1:
            if notes:
                find(notes, "plan", k)
        else:
            find(m["content"], "writer" if m["role"] == "user" else "assistant", k)

    split = {"writer": 0.0, "assistant": 0.0, "plan": 0.0, "frame": 0.0, "located": located,
             "turns": [{"role": m["role"], "bits": 0.0} for m in messages[:-1]]}
    draft_toks, P = [], len(prefix)
    for at, b in toks:
        if at >= P:
            draft_toks.append((at - P, b))
            continue
        seg = next((s for s in segs if s[0] <= at < s[1]), None)
        if seg is None:
            split["frame"] += b
            continue
        split[seg[2]] += b
        if seg[2] != "plan":
            split["turns"][seg[3]]["bits"] += b
    return split, draft_toks
