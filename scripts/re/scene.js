// usage: node scene.js <chunk.js>  -> prints structure of the embedded JSON.parse('...') payload
const fs = require("fs");
const s = fs.readFileSync(process.argv[2], "utf8");
const start = s.indexOf("JSON.parse('") + 12;
const end = s.lastIndexOf("')");
const raw = s.slice(start, end).replace(/\\'/g, "'").replace(/\\\\/g, "\\");
let j;
try { j = JSON.parse(raw); } catch (e) { console.log("parse fail", e.message, raw.slice(0, 200)); process.exit(1); }
function shape(o, d = 0) {
  if (Array.isArray(o)) return `Array(${o.length})` + (o.length && d < 3 ? ` of ${shape(o[0], d + 1)}` : "");
  if (o && typeof o === "object") return "{" + Object.keys(o).slice(0, 25).map(k => `${k}: ${d < 3 ? shape(o[k], d + 1) : typeof o[k]}`).join(", ") + "}";
  return typeof o === "string" ? JSON.stringify(o.slice(0, 40)) : String(o);
}
console.log(shape(j));
if (j.transforms) {
  const names = j.transforms.map(t => t.name);
  console.log("transform count", names.length);
  console.log("names sample:", [...new Set(names)].filter(n => /cam|point|hotspot|path|light|spot|poi|nav|view|target/i.test(n)).slice(0, 80).join(" | "));
}
if (j.objects) {
  console.log("objects", j.objects.length, "static", j.objects.filter(o => o.isStatic).length);
  const mats = {}; for (const o of j.objects) mats[o.material] = (mats[o.material] || 0) + 1;
  console.log("materials", Object.entries(mats).sort((a, b) => b[1] - a[1]).slice(0, 40).map(([k, v]) => k + ":" + v).join(", "));
}
for (const k of Object.keys(j)) if (!["transforms", "objects"].includes(k)) console.log("KEY", k, JSON.stringify(j[k]).slice(0, 600));
