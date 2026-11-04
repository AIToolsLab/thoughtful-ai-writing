// ============================================================
// CONFIG TEMPLATE — copy this file to config.js and fill in
// your own values. config.js is gitignored and never committed.
//
//   cp config.example.js config.js
//
// Then edit config.js and paste your API key.
// ============================================================
window.DEEPSEEK_CONFIG = {
  // Local CORS proxy (start with: node deepseek-proxy.js).
  // The proxy forwards to the school's DeepSeek server and adds CORS headers.
  url: "http://localhost:3000",
  // Model id served by the local endpoint.
  model: "deepseek-ai/DeepSeek-V4-Flash-0731",
  // Your API key. Keep this private — it is only read from this local file.
  apiKey: "PASTE_YOUR_API_KEY_HERE",
};
