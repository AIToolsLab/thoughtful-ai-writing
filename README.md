# Thoughtful AI Writing

A human-centered AI writing tool that helps users compose text through interactive word and phrase selection, keeping humans in control of the writing process.

## Bit Meter prototype

[`bit_meter.html`](./bit_meter.html) is a self-contained prototype writing assistant that **scores every word in bits** and shows how many of those bits came from the writer versus the AI. It makes the human's contribution to a text visible and measurable.

### How it works

- Every piece of text is measured in **bits**: how surprising it is to the language model, which is the amount of information it carries.
- Words you type count as **your** bits. Choosing an option counts the information in your choice. Grey text you accept and generated text count as **AI** bits.
- A **meter** shows your human share, a **bits-per-word strip** shows each word's bits, and **Bits by part** splits everything the model read between you and the AI (see below).

### Two models

| Job | Model | Server |
|---|---|---|
| Writing suggestions, bit scores, the meter | Qwen 3.8 | Prof. Arnold's vLLM server, `https://vllm.thoughtful-ai.com` |
| Chat replies | DeepSeek (falls back to Qwen) | Calvin's Open WebUI, through the local proxy |

Predictions use the token engine from Prof. Arnold's [writing-prototypes](https://github.com/AIToolsLab/writing-prototypes) (`docs/llm.js`, `docs/engine-tokens.js`): chat-format prompts with thinking off, token healing for half-typed words, and whole-word options with probabilities.

### Features

- **Three writing modes:** Assisted (grey text + choices), Plain typing, and Generate paragraphs.
- **Your plan** (formerly the Thinking Box): what you want to say. The model reads it as your request in a chat; you write the reply and the model only predicts.
- **Suggestions:** `Tab` accepts the next grey word, `Shift`+`Tab` the whole grey phrase, `Alt`+`1`–`5` (`⌥` on Mac) picks an option, keep typing to narrow the options, `Esc` hides them. When the model is unsure (a "fork"), the grey text disappears and you choose.
- **Chat panel:** ask about your draft; the conversation steers the suggestions and is part of the bit split.
- **Measure what the plan saved:** scores the text with and without the plan.
- **Select and delete:** drag over words in the draft, then press Backspace or Delete.
- **Settings:** fork threshold, grey-text length, number of options, words per option, pick keys.
- **Session log:** copy or download every session as JSON for `score_sessions.py`.

### Usage

Open `bit_meter.html` in a browser. It connects to the class Qwen server on load; the model name and response time appear under the writing box. If the server can't be reached, a banner says so and **Try again** reconnects. There is no offline model. For chat through DeepSeek, also follow the setup below.

### How the bits are split (writer vs. AI)

The model reads one long prompt, in this order:

1. the chat turns: the writer's messages and the AI's replies,
2. the request with the writer's plan,
3. the draft.

`bit_meter.html` scores this whole prompt in one pass and adds up each token's bits by the part it falls in (each token belongs to its first non-space character):

| Part | Was (old tags) | Counted as |
|---|---|---|
| Your chat messages | `<writer>` | you |
| Your plan | `<notes>` | you |
| The draft, word by word | `<draft>` | you or AI, by how each word got in |
| AI chat replies | `<assistant>` | AI |
| Template markup and the fixed request wording | — | not counted |

Each part is scored *given everything before it*. So if an AI reply suggests an idea and you then write it, that idea is counted once, as AI bits in the reply, and your draft gets cheaper. If you bring the idea yourself, it shows up as your bits.

The meter shows **Human share of plan + text** (the original measure), **Human share including the chat**, and a **Bits by part** table. Each chat bubble shows its own bits. The parts always add up to the score of the whole prompt.

Known issue: Qwen scores DeepSeek's replies, so a reply worded unlike Qwen counts as many AI bits even if none of it was used. Measuring only what the replies changed in the draft would fix this; it is a next step.

### Analysis scripts

| File | What it does |
|---|---|
| `score_sessions.py` | Rescores session logs with the same split and draws the speed-vs-control chart. `sessions.csv` includes `chat_writer_bits`, `chat_assistant_bits`, `control_with_chat`. |
| `notes_sweep.py` | Scores one finished text under several versions of the plan. |
| `qwen_chat.py` | Shared helper used by both scripts: the same chat format, scoring and split as the page. |
| `examples/` | A sample paragraph and plan versions for `notes_sweep.py`. |

```bash
python score_sessions.py logs/*.json
python notes_sweep.py examples/essay.txt examples/notes_versions.txt
```

### Chat & configuration

The **Chat** panel (collapsible, VS Code-style) lets you talk to the model, and the conversation steers the writing suggestions. Chat prefers the school's locally-deployed **DeepSeek** API and falls back to the class vLLM server if it's unavailable.

#### Setting up the DeepSeek chat backend

The DeepSeek API key is **private**, so it lives in a local `config.js` file that is **never committed to git**. To set it up:

**Step 1 — Create your local config from the template**

- **macOS / Linux:**
  ```bash
  cp config.example.js config.js
  ```
- **Windows (PowerShell):**
  ```powershell
  Copy-Item config.example.js config.js
  ```

**Step 2 — Add your API key**

Open `config.js` and replace `PASTE_YOUR_API_KEY_HERE` with your real key:

```js
window.DEEPSEEK_CONFIG = {
  url: "http://localhost:3000",   // local CORS proxy (see below)
  model: "deepseek-ai/DeepSeek-V4-Flash-0731",
  apiKey: "YOUR_REAL_KEY_HERE",   // ← paste your key here
};
```

**Step 3 — Start the CORS proxy**

The school's DeepSeek server (Open WebUI) doesn't send CORS headers, so browsers block cross-origin requests. A tiny local proxy forwards requests and adds the needed headers. Start it in a terminal (keep it running):

```bash
node deepseek-proxy.js
```

You should see: `DeepSeek CORS proxy running at http://localhost:3000`

**Step 4 — Open the app**

Open `bit_meter.html` in a browser. The Chat panel will now use DeepSeek (through the proxy) first, and fall back to the class vLLM server if DeepSeek is unreachable.

> **Why two files?** `config.example.js` is committed as a template so anyone can clone the repo and copy it. `config.js` holds your private key and is ignored by git (see `.gitignore`), so your key is never uploaded to GitHub.

### Project status

Working prototype for the senior project (final presentation December 2026). Predictions, scoring and the bit split run on the class Qwen server; the chat runs on DeepSeek when the proxy is set up.
