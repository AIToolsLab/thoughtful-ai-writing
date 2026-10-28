# Thoughtful AI Writing

A human-centered AI writing tool that helps users compose text through interactive word and phrase selection, keeping humans in control of the writing process.

## Bit Meter prototype

[`bit_meter.html`](./bit_meter.html) is a self-contained prototype writing assistant that **scores every word in bits** and shows how many of those bits came from the writer versus the AI. It makes the human's contribution to a text visible and measurable.

### How it works

- Every word you type is measured in **bits** — the amount of information you supplied.
- Words you choose yourself count as **your** bits; words suggested and accepted from the AI count as **AI** bits.
- A **meter** shows your "human share" of all bits, and a **bits-per-word strip** reads like the text itself, color-coding each word by its source.

### Features

- **Three writing modes**: Assisted (ghost text + choices), Plain typing, and Generate paragraphs.
- **Thinking Box**: notes that steer the AI's suggestions.
- **Live meter** showing your human share of all bits, plus a per-word bit strip.
- **Interactive suggestions**: `Tab` accepts the next word, `Shift`+`Tab` accepts the grey phrase, `Alt`+`1`–`4` (or `1`–`4` at a fork) chooses an option, typing letters filters suggestions, and `Esc` hides them.
- **Two backends**:
  - **Built-in demo model** — a trigram model that runs entirely in the page (no server needed).
  - **Class vLLM server (Qwen)** — connect to a remote vLLM endpoint for real model suggestions.
- **Adjustable settings**: bit threshold, ghost-word length, number of choice options, and pick-key style.
- **Session logging**: copy or download the full session log as JSON.

### Usage

Open `bit_meter.html` in a browser. For the demo model, no setup is required — just start writing. To use the vLLM backend, enter the server URL and model, then click **Connect**.

### Chat & configuration

The **Chat** panel (collapsible, VS Code-style) lets you talk to the model, and the conversation steers the writing suggestions. Chat prefers the school's locally-deployed **DeepSeek** API and falls back to the class vLLM server if it's unavailable.

To use the DeepSeek chat backend, create your local config from the template:

```bash
cp config.example.js config.js
```

Then open `config.js` and paste your API key into `apiKey`. **`config.js` is gitignored and never committed** — it holds your private key. The committed `config.example.js` is just a template for others to copy.

### Project status

Early prototype. The Bit Meter is a working demo; the broader thoughtful-ai-writing tool is under active development.
