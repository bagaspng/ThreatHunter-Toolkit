"use strict";

const edInput = document.getElementById("ed-input");
const edLive = document.getElementById("ed-live");
const obInput = document.getElementById("ob-input");
const obFile = document.getElementById("ob-file");
const obCard = document.getElementById("ob-card");
// EXT: deteksi tipe dari ekstensi file saat UPLOAD (.css -> obfuscate CSS).
const EXT = { js: "js", css: "css", py: "py", html: "html", htm: "html" };
// Nama & MIME file saat UNDUH. Catatan: obfuscate CSS menghasilkan JavaScript
// (injector yang menyuntik CSS ke DOM), jadi diunduh sebagai .css.js — bukan .css.
const DL_NAME = { js: "obfuscated.js", css: "obfuscated.css.js",
                  py: "obfuscated.py", html: "obfuscated.html" };
const DL_MIME = { js: "text/javascript", css: "text/javascript",
                  py: "text/x-python", html: "text/html" };

// ---- Toast ---------------------------------------------------------------
function toast(msg) {
  const wrap = document.getElementById("toast-wrap");
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  wrap.appendChild(t);
  requestAnimationFrame(function () { t.classList.add("show"); });
  setTimeout(function () {
    t.classList.remove("show");
    setTimeout(function () { t.remove(); }, 250);
  }, 1600);
}

// ---- Counter karakter/byte ----------------------------------------------
function byteLen(s) { return new TextEncoder().encode(s).length; }
function updateCounter(inputId, countId) {
  const v = document.getElementById(inputId).value;
  document.getElementById(countId).textContent =
    v.length + " karakter · " + byteLen(v) + " byte";
}

// ---- Segmented control (tipe obfuscate) ----------------------------------
document.querySelectorAll("#ob-type .seg-btn").forEach(function (b) {
  b.addEventListener("click", function () { setType(b.dataset.val); });
});
function setType(val) {
  document.querySelectorAll("#ob-type .seg-btn").forEach(function (x) {
    x.classList.toggle("active", x.dataset.val === val);
  });
}
function obType() {
  return document.querySelector("#ob-type .seg-btn.active").dataset.val;
}

// ---- Output helpers ------------------------------------------------------
function setOut(id, text, empty) {
  const el = document.getElementById(id);
  el.textContent = text;
  el.classList.toggle("empty", !!empty);
}
function showError(id, msg) {
  const el = document.getElementById(id);
  el.classList.remove("empty");
  el.textContent = "";
  const box = document.createElement("div");
  box.className = "error-box";
  box.textContent = msg;
  el.appendChild(box);
}
function loading(btnId, on) {
  const b = document.getElementById(btnId);
  if (b) b.classList.toggle("loading", on);
}

// ---- Copy ----------------------------------------------------------------
async function copyOut(id) {
  const el = document.getElementById(id);
  if (el.classList.contains("empty")) return;
  try {
    await navigator.clipboard.writeText(el.textContent);
    toast("Disalin ke clipboard");
  } catch (e) {}
}
function copyText(text, btn) {
  navigator.clipboard.writeText(text).then(function () {
    const prev = btn.textContent;
    btn.textContent = "Tersalin";
    btn.classList.add("done");
    toast("Disalin ke clipboard");
    setTimeout(function () {
      btn.textContent = prev; btn.classList.remove("done");
    }, 1200);
  }).catch(function () {});
}

// ---- Render hasil encode/decode per metode -------------------------------
function renderSection(label, obj) {
  const sect = document.createElement("div");
  sect.className = "sect";
  const entries = Object.entries(obj);
  let ok = 0, fail = 0;
  entries.forEach(function (e) { e[1].ok ? ok++ : fail++; });

  const head = document.createElement("div");
  head.className = "sect-label";
  head.textContent = label + " · " + ok + " berhasil"
    + (fail ? ", " + fail + " gagal" : "");
  sect.appendChild(head);

  for (const [name, item] of entries) {
    const row = document.createElement("div");
    row.className = "mrow" + (item.ok ? "" : " fail");
    const key = document.createElement("div");
    key.className = "mrow-key";
    key.textContent = name;
    const val = document.createElement("div");
    val.className = "mrow-val";
    val.textContent = item.ok ? item.value : "[gagal] " + item.error;
    row.appendChild(key);
    row.appendChild(val);
    if (item.ok) {
      const send = document.createElement("button");
      send.className = "msend";
      send.textContent = "→ input";
      send.title = "Kirim nilai ini ke kotak input";
      send.addEventListener("click", function () {
        edInput.value = item.value;
        updateCounter("ed-input", "ed-count");
        translateText();
        edInput.focus();
      });
      const btn = document.createElement("button");
      btn.className = "mcopy";
      btn.textContent = "Salin";
      btn.addEventListener("click", function () { copyText(item.value, btn); });
      row.appendChild(send);
      row.appendChild(btn);
    }
    sect.appendChild(row);
  }
  return sect;
}

// ---- Encode & Decode -----------------------------------------------------
async function translateText() {
  const out = document.getElementById("ed-out");
  const text = edInput.value;
  if (!text) {
    out.classList.add("empty");
    out.textContent = "Hasil encode dan decode akan muncul di sini.";
    return;
  }
  loading("ed-run", true);
  out.classList.remove("empty");
  out.textContent = "Memproses...";
  try {
    const res = await fetch("/api/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text })
    });
    const data = await res.json();
    if (data.error) { showError("ed-out", data.error); return; }
    out.textContent = "";
    out.appendChild(renderSection("Encode", data.encode));
    out.appendChild(renderSection("Decode", data.decode));
  } catch (e) {
    showError("ed-out", "Gagal terhubung ke server.");
  } finally {
    loading("ed-run", false);
  }
}
function clearEd() {
  edInput.value = "";
  updateCounter("ed-input", "ed-count");
  const out = document.getElementById("ed-out");
  out.classList.add("empty");
  out.textContent = "Hasil encode dan decode akan muncul di sini.";
  edInput.focus();
}

// Live mode: proses otomatis saat mengetik (debounce)
let edTimer = null;
edInput.addEventListener("input", function () {
  updateCounter("ed-input", "ed-count");
  if (!edLive.checked) return;
  clearTimeout(edTimer);
  edTimer = setTimeout(translateText, 350);
});
edLive.addEventListener("change", function () {
  if (edLive.checked && edInput.value) translateText();
});
// Toggle "tampilkan yang gagal"
document.getElementById("ed-showfail").addEventListener("change", function (e) {
  document.getElementById("ed-out").classList.toggle("show-fail", e.target.checked);
});
// Ctrl/Cmd+Enter untuk memproses
edInput.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault(); translateText();
  }
});

// ---- Obfuscate -----------------------------------------------------------
let lastObf = null; // { result, type }

function loadFile(f) {
  if (!f) return;
  document.getElementById("ob-file-name").textContent = f.name;
  const ext = f.name.split(".").pop().toLowerCase();
  if (EXT[ext]) setType(EXT[ext]);
  const reader = new FileReader();
  reader.onload = function () {
    obInput.value = reader.result;
    updateCounter("ob-input", "ob-count");
    toast("File dimuat: " + f.name);
  };
  reader.readAsText(f);
}
obFile.addEventListener("change", function () { loadFile(obFile.files[0]); });

// Drag & drop file ke kartu Obfuscate
["dragenter", "dragover"].forEach(function (ev) {
  obCard.addEventListener(ev, function (e) {
    e.preventDefault();
    obCard.classList.add("dragover");
  });
});
obCard.addEventListener("dragleave", function (e) {
  if (obCard.contains(e.relatedTarget)) return;
  obCard.classList.remove("dragover");
});
obCard.addEventListener("drop", function (e) {
  e.preventDefault();
  obCard.classList.remove("dragover");
  const f = e.dataTransfer.files[0];
  if (f) loadFile(f);
});

async function obfuscate() {
  const code = obInput.value;
  if (!code) { showError("ob-out", "Kode kosong."); return; }
  loading("ob-run", true);
  setOut("ob-out", "Memproses...", true);
  document.getElementById("ob-meta").textContent = "Hasil";
  document.getElementById("ob-dl").disabled = true;
  try {
    const res = await fetch("/api/obfuscate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code, type: obType() })
    });
    const data = await res.json();
    if (data.error) { showError("ob-out", data.error); return; }
    const kind = data.type === "css" ? "css → JS injector" : data.type;
    const meta = kind + " · " + (data.result ? data.result.length : 0)
      + " karakter" + (data.verify ? (data.verify.ok ? " · verify OK"
                                                      : " · verify WARN") : "");
    document.getElementById("ob-meta").textContent = meta;
    setOut("ob-out", data.result || JSON.stringify(data, null, 2), false);
    lastObf = { result: data.result || "", type: data.type };
    document.getElementById("ob-dl").disabled = !data.result;
  } catch (e) {
    showError("ob-out", "Gagal terhubung ke server.");
  } finally {
    loading("ob-run", false);
  }
}
function clearOb() {
  obInput.value = "";
  updateCounter("ob-input", "ob-count");
  document.getElementById("ob-file-name").textContent = "";
  const out = document.getElementById("ob-out");
  out.classList.add("empty");
  out.textContent = "Hasil obfuscate akan muncul di sini.";
  document.getElementById("ob-dl").disabled = true;
  lastObf = null;
  obInput.focus();
}
obInput.addEventListener("input", function () {
  updateCounter("ob-input", "ob-count");
});
obInput.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault(); obfuscate();
  }
});

function downloadResult() {
  if (!lastObf || !lastObf.result) return;
  const name = DL_NAME[lastObf.type] || "obfuscated.txt";
  const mime = (DL_MIME[lastObf.type] || "text/plain") + ";charset=utf-8";
  const blob = new Blob([lastObf.result], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  toast("File diunduh");
}

// ---- Inisialisasi --------------------------------------------------------
updateCounter("ed-input", "ed-count");
updateCounter("ob-input", "ob-count");
