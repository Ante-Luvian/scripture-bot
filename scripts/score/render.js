// Draws chant scores in square notation: node render.js jobs.json
// jobs.json: [{"gabc": "...", "out": "path.png"}, ...]. Each score is laid out by exsurge
// (exsurge.min.js: github.com/bbloomf/exsurge, MIT) in a jsdom page, and drawn with node-canvas,
// which also measures the lyrics, so the text is set in the font it was measured in.
const fs = require("fs");
const { JSDOM } = require("jsdom");
const { createCanvas, loadImage } = require("canvas");

const dom = new JSDOM("<!doctype html><html><head></head><body></body></html>", { pretendToBeVisual: true });
for (const k of ["window", "document", "navigator", "Node", "Element", "HTMLElement", "SVGElement",
                 "XMLSerializer", "DOMParser"])
  global[k] = k === "window" ? dom.window : dom.window[k];
const exsurge = require("./exsurge.min.js");

const WIDTH = 1000;          // the layout width, in CSS pixels
const MARGIN = 28;
const SCALE = 2;             // drawn at twice that, for phone screens
const PAPER = "#fffdf8";

function layout(gabc) {
  const ctxt = new exsurge.ChantContext();
  ctxt.lyricTextFont = "'Times New Roman'";
  ctxt.lyricTextSize = 18;
  const score = new exsurge.ChantScore(ctxt, exsurge.Gabc.createMappingsFromSource(ctxt, gabc), false);
  score.performLayout(ctxt);
  return new Promise(resolve => score.layoutChantLines(ctxt, WIDTH - 2 * MARGIN, () => resolve(score.createSvg(ctxt))));
}

async function draw(gabc, out) {
  let svg = await layout(gabc);
  svg = typeof svg === "string" ? svg : svg.outerHTML;
  const h = parseFloat(svg.match(/height="([\d.]+)"/)[1]);
  // the custos at a line's end overhangs the layout width; widen the SVG's viewport so it isn't clipped
  const w = parseFloat(svg.match(/width="([\d.]+)"/)[1]) + 16;
  svg = svg.replace(/width="[\d.]+"/, `width="${w}"`).replace(/viewBox="0 0 [\d.]+ /, `viewBox="0 0 ${w} `);
  const canvas = createCanvas(Math.ceil((w + 2 * MARGIN + 12) * SCALE), Math.ceil((h + 2 * MARGIN) * SCALE));
  const g = canvas.getContext("2d");
  g.fillStyle = PAPER;
  g.fillRect(0, 0, canvas.width, canvas.height);
  const img = await loadImage(Buffer.from(svg));
  g.drawImage(img, MARGIN * SCALE, MARGIN * SCALE, w * SCALE, h * SCALE);
  fs.writeFileSync(out, canvas.toBuffer("image/png"));
}

(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
  let ok = 0;
  for (const job of jobs) {
    try {
      await draw(job.gabc, job.out);
      ok++;
    } catch (e) {
      console.log(`failed ${job.out}: ${String(e).slice(0, 120)}`);
    }
  }
  console.log(`drew ${ok} of ${jobs.length}`);
})();
