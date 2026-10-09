// Generates pre-compressed .br and .gz siblings for every hashed JS/CSS asset
// in dist/assets so the Django view can serve them with the matching
// Content-Encoding. Uses only Node's built-in zlib — no extra dependencies.
//
// Runs automatically as part of `npm run build`. On PythonAnywhere the built
// (and compressed) dist/ is committed, so no build step is needed there.
import { readdirSync, statSync, readFileSync, writeFileSync, existsSync, rmSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { brotliCompressSync, gzipSync, constants } from "node:zlib";

const dir = fileURLToPath(new URL("../dist/assets/", import.meta.url));
const QUALITY = constants.BROTLI_PARAM_QUALITY ?? 11;

let count = 0;
for (const name of readdirSync(dir)) {
  if (!/\.(js|css)$/.test(name)) continue;
  const src = dir + name;
  const st = statSync(src);
  const input = readFileSync(src);

  // Brotli (best ratio, preferred by all modern browsers).
  const brSrc = src + ".br";
  if (!existsSync(brSrc) || statSync(brSrc).mtimeMs < st.mtimeMs) {
    const out = brotliCompressSync(input, { params: { [QUALITY]: 11 } });
    if (out.length < input.length) writeFileSync(brSrc, out);
    else if (existsSync(brSrc)) rmSync(brSrc, { force: true });
  }

  // Gzip fallback for clients without brotli.
  const gzSrc = src + ".gz";
  if (!existsSync(gzSrc) || statSync(gzSrc).mtimeMs < st.mtimeMs) {
    const out = gzipSync(input, { level: 9 });
    if (out.length < input.length) writeFileSync(gzSrc, out);
    else if (existsSync(gzSrc)) rmSync(gzSrc, { force: true });
  }
  count++;
}
console.log(`compress-dist: processed ${count} asset(s) -> .br + .gz`);

