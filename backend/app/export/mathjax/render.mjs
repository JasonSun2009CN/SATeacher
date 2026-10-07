// TeX -> self-contained SVG bridge for the exporter.
//
// Reads a JSON array `[{"tex": "...", "display": false}, ...]` from stdin and
// writes a JSON array of SVG strings (null when a formula could not be parsed)
// to stdout. Run with:  node render.mjs < input.json
//
// This is optional: the Python exporter degrades to plain text when Node or
// this bridge is unavailable (see app/export/math_render.py).

import { mathjax } from "mathjax-full/js/mathjax.js";
import { TeX } from "mathjax-full/js/input/tex.js";
import { SVG } from "mathjax-full/js/output/svg.js";
import { liteAdaptor } from "mathjax-full/js/adaptors/liteAdaptor.js";
import { RegisterHTMLHandler } from "mathjax-full/js/handlers/html.js";
import { AllPackages } from "mathjax-full/js/input/tex/AllPackages.js";

const adaptor = liteAdaptor();
RegisterHTMLHandler(adaptor);
const tex = new TeX({ packages: AllPackages });
const svg = new SVG({ fontCache: "local" });
const doc = mathjax.document("", { InputJax: tex, OutputJax: svg });

let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  let request;
  try {
    request = JSON.parse(input);
  } catch {
    process.stderr.write("invalid JSON input\n");
    process.exit(2);
  }
  const items = Array.isArray(request) ? request : [request];
  const out = items.map((item) => {
    try {
      const node = doc.convert(String(item.tex ?? ""), { display: !!item.display });
      return adaptor.innerHTML(node);
    } catch {
      return null;
    }
  });
  process.stdout.write(JSON.stringify(out));
});