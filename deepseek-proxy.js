// Local CORS proxy for the DeepSeek chat backend.
// The school's Open WebUI server doesn't send CORS headers, so browsers block
// cross-origin requests. This tiny proxy forwards requests to DeepSeek from the
// server side (no CORS restriction) and adds the needed CORS headers back.
//
// Usage:
//   node deepseek-proxy.js
// Then open bit_meter.html and set the DeepSeek URL in config.js to:
//   http://localhost:3000
//
// The proxy forwards /api/chat/completions to https://localai.calvin.edu/api/chat/completions
// and injects the API key from config.js (or the DEEPSEEK_API_KEY env var).

const http = require("http");
const https = require("https");
const fs = require("fs");
const path = require("path");

const PORT = process.env.PORT || 3000;
const TARGET = process.env.DEEPSEEK_TARGET || "https://localai.calvin.edu";

// Read the API key from config.js if present, else from env.
function loadApiKey() {
  if (process.env.DEEPSEEK_API_KEY) return process.env.DEEPSEEK_API_KEY;
  try {
    const cfgPath = path.join(__dirname, "config.js");
    const src = fs.readFileSync(cfgPath, "utf8");
    const m = src.match(/apiKey\s*:\s*"([^"]+)"/);
    if (m && m[1] && m[1] !== "PASTE_YOUR_API_KEY_HERE") return m[1];
  } catch (e) { /* ignore */ }
  return null;
}

const API_KEY = loadApiKey();

function corsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Authorization",
    "Access-Control-Max-Age": "86400",
  };
}

const server = http.createServer((req, res) => {
  // Handle CORS preflight
  if (req.method === "OPTIONS") {
    res.writeHead(204, corsHeaders());
    res.end();
    return;
  }

  // Only forward the chat completions path
  if (!req.url.startsWith("/api/chat/completions")) {
    res.writeHead(404, { "Content-Type": "application/json", ...corsHeaders() });
    res.end(JSON.stringify({ error: "Not found. Use /api/chat/completions" }));
    return;
  }

  let body = "";
  req.on("data", (chunk) => { body += chunk; });
  req.on("end", () => {
    // Parse the incoming JSON to inject the API key and model if needed
    let payload = {};
    try { payload = JSON.parse(body || "{}"); } catch (e) { /* keep empty */ }

    const outbound = JSON.stringify(payload);

    const targetUrl = new URL(TARGET + "/api/chat/completions");
    const headers = {
      "Content-Type": "application/json",
      "Content-Length": Buffer.byteLength(outbound),
    };
    if (API_KEY) headers["Authorization"] = "Bearer " + API_KEY;

    const proxyReq = https.request({
      hostname: targetUrl.hostname,
      port: targetUrl.port || 443,
      path: targetUrl.pathname + targetUrl.search,
      method: "POST",
      headers,
    }, (proxyRes) => {
      // Forward status and content-type, plus CORS headers
      res.writeHead(proxyRes.statusCode, {
        "Content-Type": proxyRes.headers["content-type"] || "application/json",
        ...corsHeaders(),
      });
      proxyRes.pipe(res);
    });

    proxyReq.on("error", (err) => {
      res.writeHead(502, { "Content-Type": "application/json", ...corsHeaders() });
      res.end(JSON.stringify({ error: "Proxy error: " + err.message }));
    });

    proxyReq.write(outbound);
    proxyReq.end();
  });
});

server.listen(PORT, () => {
  console.log(`DeepSeek CORS proxy running at http://localhost:${PORT}`);
  console.log(`Forwarding to ${TARGET}/api/chat/completions`);
  console.log(`API key: ${API_KEY ? "loaded" : "NOT SET (set DEEPSEEK_API_KEY or config.js)"}`);
});
