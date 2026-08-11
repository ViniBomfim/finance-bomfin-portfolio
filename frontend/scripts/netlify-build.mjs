/**
 * No deploy Netlify: gera public/_redirects (proxy /api → backend se API_PROXY_TARGET existir).
 */
import { writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const publicDir = join(__dirname, "..", "public");
const isNetlify = process.env.NETLIFY === "true";

const raw = (process.env.API_PROXY_TARGET || process.env.VITE_API_URL || "").trim();

function normalizeProxyBase(url) {
  const base = url.replace(/\/+$/, "");
  const lower = base.toLowerCase();
  if (lower.endsWith("/api/v1")) return base.slice(0, -3);
  if (lower.endsWith("/api")) return base;
  return `${base}/api`;
}

if (!isNetlify) {
  process.exit(0);
}

const spaFallback = "/*    /index.html   200\n";

if (!raw) {
  writeFileSync(join(publicDir, "_redirects"), `# SPA (sem proxy — defina API_PROXY_TARGET no Netlify)\n${spaFallback}`, "utf8");
  console.warn(
    "\n[netlify-build] AVISO: API_PROXY_TARGET não definida.\n" +
      "O build conclui, mas o login não funcionará até você adicionar em\n" +
      "Site settings → Environment variables, ex.:\n" +
      "  API_PROXY_TARGET=https://sua-api.onrender.com\n" +
      "Depois: Trigger deploy → Clear cache and deploy.\n",
  );
  process.exit(0);
}

const proxyBase = normalizeProxyBase(raw);
const redirects = `# Gerado no build — proxy para o backend
/api/*  ${proxyBase}/:splat  200
${spaFallback}`;

writeFileSync(join(publicDir, "_redirects"), redirects, "utf8");
console.log(`[netlify-build] Proxy: /api/* → ${proxyBase}/:splat`);
