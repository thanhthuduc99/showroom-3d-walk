// usage: node shaders.js <bundle.js> [filterRegex]
const fs = require("fs");
const s = fs.readFileSync(process.argv[2], "utf8");
const filter = process.argv[3] ? new RegExp(process.argv[3]) : null;
const re = /(["'`])((?:(?!\1)[^\\]|\\.){60,}?)\1/g;
let m, k = 0;
while ((m = re.exec(s))) {
  const t = m[2];
  if (!/gl_FragColor|gl_Position|varying |uniform sampler/.test(t)) continue;
  const body = t.replace(/\\n/g, "\n").replace(/\\t/g, "  ");
  if (filter && !filter.test(body)) continue;
  k++;
  const before = s.slice(Math.max(0, m.index - 120), m.index).replace(/\s+/g, " ");
  console.log(`\n### #${k} @${m.index} len=${t.length}\nctx: ${before}\n${body}`);
}
console.error("matched", k);
