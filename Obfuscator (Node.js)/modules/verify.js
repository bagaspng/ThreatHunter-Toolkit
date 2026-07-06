"use strict";

const fs = require("fs");
const { TextDecoder } = require("util");

let JSDOM;
try {
  JSDOM = require("jsdom").JSDOM;
} catch (e) {
  console.error("jsdom belum terpasang. Jalankan: npm install jsdom");
  process.exit(2);
}

function extractScript(html) {
  const open = html.indexOf("<script>");
  const close = html.indexOf("</script>", open);
  if (open === -1 || close === -1) {
    throw new Error("tidak menemukan blok <script> di output");
  }
  return html.slice(open + "<script>".length, close);
}

function main() {
  const [outFile, expectedFile] = process.argv.slice(2);
  if (!outFile || !expectedFile) {
    console.error("Usage: node verify.js <obfuscatedHtml> <expectedRendered>");
    process.exit(2);
  }

  const obfuscated = fs.readFileSync(outFile, "utf8");
  const expected = fs.readFileSync(expectedFile, "utf8");
  const script = extractScript(obfuscated);

  const dom = new JSDOM("<!DOCTYPE html><html><head></head><body></body></html>", {
    runScripts: "dangerously",
  });
  const win = dom.window;

  win.TextDecoder = TextDecoder;
  win.Uint8Array = Uint8Array;

  const writes = [];
  win.document.open = function () { writes.length = 0; return win.document; };
  win.document.write = function (s) { writes.push(String(s)); };
  win.document.writeln = function (s) { writes.push(String(s) + "\n"); };
  win.document.close = function () {};

  try {
    win.eval(script);
  } catch (err) {
    console.error("MISMATCH: loader melempar error -> " + err.message);
    process.exit(1);
  }

  const captured = writes.join("");
  if (captured === expected) {
    console.log("MATCH");
    process.exit(0);
  }

  let i = 0;
  const n = Math.min(captured.length, expected.length);
  while (i < n && captured[i] === expected[i]) i++;
  console.error(
    "MISMATCH: len captured=" + captured.length +
    " expected=" + expected.length +
    " first diff @" + i
  );
  process.exit(1);
}

main();
