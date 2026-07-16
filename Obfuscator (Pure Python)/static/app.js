"use strict";

const edInput = document.getElementById("ed-input");
const edLive = document.getElementById("ed-live");
const obInput = document.getElementById("ob-input");
const obFile = document.getElementById("ob-file");
const obCard = document.getElementById("ob-card");
const EXT = { js: "js", css: "css", py: "py", html: "html", htm: "html" };
const DL_NAME = { js: "obfuscated.js", css: "obfuscated.css.js",
                  py: "obfuscated.py", html: "obfuscated.html" };
const DL_MIME = { js: "text/javascript", css: "text/javascript",
                  py: "text/x-python", html: "text/html" };

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

function byteLen(s) { return new TextEncoder().encode(s).length; }
function updateCounter(inputId, countId) {
  const v = document.getElementById(inputId).value;
  document.getElementById(countId).textContent =
    v.length + " karakter · " + byteLen(v) + " byte";
}

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

function renderSection(label, obj, isDecode) {
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
    if (isDecode && item.ok && item.hint && item.hint.again) {
      sect.appendChild(makeHint(item.value, item.hint));
    }
  }
  return sect;
}

function sendToInput(value) {
  edInput.value = value;
  updateCounter("ed-input", "ed-count");
  translateText();
  edInput.focus();
}

function makeHint(value, hint) {
  const bar = document.createElement("div");
  bar.className = "hintbar";

  const pill = document.createElement("span");
  pill.className = "hint-pill";
  pill.textContent = "↻ mungkin masih " + (hint.guess || "bisa di-decode");
  bar.appendChild(pill);

  const again = document.createElement("button");
  again.className = "hint-btn";
  again.textContent = "Decode lagi";
  again.addEventListener("click", function () { sendToInput(value); });
  bar.appendChild(again);

  const peel = document.createElement("button");
  peel.className = "hint-btn";
  peel.textContent = "Kupas semua";
  peel.addEventListener("click", function () { runPeel(value, bar); });
  bar.appendChild(peel);

  return bar;
}

async function runPeel(value, bar) {
  try {
    const res = await fetch("/api/peel", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: value })
    });
    const data = await res.json();
    renderChain(bar, data.steps || []);
  } catch (e) {
    toast("Gagal terhubung ke server.");
  }
}

function renderChain(bar, steps) {
  const old = bar.nextElementSibling;
  if (old && old.classList.contains("peelchain")) old.remove();

  const box = document.createElement("div");
  box.className = "peelchain";
  const title = document.createElement("div");
  title.className = "peel-title";
  title.textContent = steps.length ? "Kupas semua" : "Tidak ada lapisan lagi.";
  box.appendChild(title);

  steps.forEach(function (st, idx) {
    const last = idx === steps.length - 1;
    const row = document.createElement("div");
    row.className = "peel-step" + (last ? " final" : "");
    const tag = document.createElement("span");
    tag.className = "peel-tag";
    tag.textContent = "lapis " + (idx + 1) + " · " + st.name;
    const val = document.createElement("span");
    val.className = "peel-val";
    val.textContent = st.value;
    row.appendChild(tag);
    row.appendChild(val);
    if (last) {
      const send = document.createElement("button");
      send.className = "hint-btn";
      send.textContent = "→ input";
      send.addEventListener("click", function () { sendToInput(st.value); });
      row.appendChild(send);
    }
    box.appendChild(row);
  });

  bar.parentNode.insertBefore(box, bar.nextSibling);
}

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
    out.appendChild(renderSection("Encode", data.encode, false));
    out.appendChild(renderSection("Decode", data.decode, true));
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
document.getElementById("ed-showfail").addEventListener("change", function (e) {
  document.getElementById("ed-out").classList.toggle("show-fail", e.target.checked);
});
edInput.addEventListener("keydown", function (e) {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault(); translateText();
  }
});

let lastObf = null;

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

const stMsg = document.getElementById("st-msg");
const stEncFile = document.getElementById("st-enc-file");
const stDecFile = document.getElementById("st-dec-file");
let lastStego = null;

document.querySelectorAll("#st-mode .seg-btn").forEach(function (b) {
  b.addEventListener("click", function () { setStegoMode(b.dataset.val); });
});
function setStegoMode(val) {
  document.querySelectorAll("#st-mode .seg-btn").forEach(function (x) {
    x.classList.toggle("active", x.dataset.val === val);
  });
  document.getElementById("st-encode-pane").hidden = val !== "encode";
  document.getElementById("st-decode-pane").hidden = val !== "decode";
  clearStego();
}

stMsg.addEventListener("input", function () {
  updateCounter("st-msg", "st-msg-count");
});
stEncFile.addEventListener("change", function () {
  const f = stEncFile.files[0];
  document.getElementById("st-enc-name").textContent = f ? f.name : "";
});
stDecFile.addEventListener("change", function () {
  const f = stDecFile.files[0];
  document.getElementById("st-dec-name").textContent = f ? f.name : "";
});

function clearStego() {
  stMsg.value = "";
  updateCounter("st-msg", "st-msg-count");
  stEncFile.value = "";
  stDecFile.value = "";
  document.getElementById("st-enc-name").textContent = "";
  document.getElementById("st-dec-name").textContent = "";
  document.getElementById("st-dl").disabled = true;
  document.getElementById("st-meta").textContent = "Hasil";
  const out = document.getElementById("st-out");
  out.classList.add("empty");
  out.textContent = "Hasil steganografi akan muncul di sini.";
  lastStego = null;
}

function stegoFigure(caption, src, revoke) {
  const fig = document.createElement("figure");
  fig.className = "st-figure";
  const cap = document.createElement("figcaption");
  cap.textContent = caption;
  const img = document.createElement("img");
  img.className = "st-preview";
  img.src = src;
  img.alt = caption;
  if (revoke) {
    img.addEventListener("load", function () { URL.revokeObjectURL(src); });
  }
  fig.appendChild(cap);
  fig.appendChild(img);
  return fig;
}

async function stegoEncode() {
  const f = stEncFile.files[0];
  if (!f) { showError("st-out", "Pilih gambar PNG pembawa dulu."); return; }
  if (!stMsg.value) { showError("st-out", "Pesan masih kosong."); return; }
  loading("st-enc-run", true);
  setOut("st-out", "Menyisipkan pesan...", true);
  const fd = new FormData();
  fd.append("file", f);
  fd.append("message", stMsg.value);
  try {
    const res = await fetch("/api/stego/encode", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) { showError("st-out", data.error); return; }
    lastStego = { dataUrl: data.image };
    const out = document.getElementById("st-out");
    out.classList.remove("empty");
    out.textContent = "";

    const beforeUrl = URL.createObjectURL(f);
    const compare = document.createElement("div");
    compare.className = "st-compare";
    compare.appendChild(stegoFigure("Asli", beforeUrl, true));
    const arrow = document.createElement("div");
    arrow.className = "st-arrow";
    arrow.textContent = "→";
    compare.appendChild(arrow);
    compare.appendChild(stegoFigure("Hasil", data.image, false));
    out.appendChild(compare);

    const info = document.createElement("div");
    info.className = "st-note";
    info.textContent = "Pesan " + data.message_len + " byte tersembunyi. Kedua gambar "
      + "tampak sama di mata — hanya bit terakhir warna yang berubah. "
      + "Unduh PNG lalu bagikan.";
    out.appendChild(info);
    document.getElementById("st-meta").textContent =
      "PNG · " + data.bytes + " byte";
    document.getElementById("st-dl").disabled = false;
    toast("Pesan berhasil disisipkan");
  } catch (e) {
    showError("st-out", "Gagal terhubung ke server.");
  } finally {
    loading("st-enc-run", false);
  }
}

async function stegoDecode() {
  const f = stDecFile.files[0];
  if (!f) { showError("st-out", "Pilih gambar PNG yang berisi pesan dulu."); return; }
  loading("st-dec-run", true);
  setOut("st-out", "Mengekstrak pesan...", true);
  const fd = new FormData();
  fd.append("file", f);
  try {
    const res = await fetch("/api/stego/decode", { method: "POST", body: fd });
    const data = await res.json();
    if (data.error) { showError("st-out", data.error); return; }
    const out = document.getElementById("st-out");
    out.classList.remove("empty");
    out.textContent = "";
    document.getElementById("st-dl").disabled = true;

    if (!data.readable) {
      const note = document.createElement("div");
      note.className = "st-note st-empty";
      note.textContent = "Tidak ada pesan terbaca. Bit LSB gambar ini acak, jadi "
        + "kemungkinan tidak ada pesan tersembunyi (atau skema penyisipannya berbeda).";
      out.appendChild(note);
      document.getElementById("st-meta").textContent = "Tidak ada pesan";
      return;
    }

    const box = document.createElement("div");
    box.className = "st-message";
    box.textContent = data.message;
    out.appendChild(box);
    const actions = document.createElement("div");
    actions.className = "row";
    const copy = document.createElement("button");
    copy.className = "mcopy";
    copy.textContent = "Salin";
    copy.addEventListener("click", function () { copyText(data.message, copy); });
    const send = document.createElement("button");
    send.className = "msend";
    send.textContent = "→ Encode/Decode";
    send.title = "Kirim ke kartu Encode & Decode (untuk kupas base64 berlapis)";
    send.addEventListener("click", function () { sendToInput(data.message); });
    actions.appendChild(copy);
    actions.appendChild(send);
    out.appendChild(actions);
    document.getElementById("st-meta").textContent =
      "Pesan · " + data.message.length + " karakter";
  } catch (e) {
    showError("st-out", "Gagal terhubung ke server.");
  } finally {
    loading("st-dec-run", false);
  }
}

function downloadStego() {
  if (!lastStego || !lastStego.dataUrl) return;
  const a = document.createElement("a");
  a.href = lastStego.dataUrl;
  a.download = "stego.png";
  document.body.appendChild(a);
  a.click();
  a.remove();
  toast("Gambar diunduh");
}

const jwtToken = document.getElementById("jwt-token");
const jwtSecret = document.getElementById("jwt-secret");
let lastJwt = null;

document.querySelectorAll("#jwt-mode .seg-btn").forEach(function (b) {
  b.addEventListener("click", function () { setJwtMode(b.dataset.val); });
});
function setJwtMode(val) {
  document.querySelectorAll("#jwt-mode .seg-btn").forEach(function (x) {
    x.classList.toggle("active", x.dataset.val === val);
  });
  document.getElementById("jwt-decode-pane").hidden = val !== "decode";
  document.getElementById("jwt-encode-pane").hidden = val !== "encode";
  clearJwt();
}
document.querySelectorAll("#jwt-alg .seg-btn").forEach(function (b) {
  b.addEventListener("click", function () {
    document.querySelectorAll("#jwt-alg .seg-btn").forEach(function (x) {
      x.classList.toggle("active", x === b);
    });
  });
});
function jwtAlg() {
  return document.querySelector("#jwt-alg .seg-btn.active").dataset.val;
}

function clearJwt() {
  jwtToken.value = "";
  jwtSecret.value = "";
  document.getElementById("jwt-payload").value = "";
  document.getElementById("jwt-enc-secret").value = "";
  document.getElementById("jwt-meta").textContent = "Hasil";
  const out = document.getElementById("jwt-out");
  out.classList.add("empty");
  out.textContent = "Hasil JWT akan muncul di sini.";
  lastJwt = null;
}

function jwtColorToken(token) {
  const parts = token.split(".");
  const box = document.createElement("div");
  box.className = "jwt-token";
  const cls = ["jwt-h", "jwt-p", "jwt-s"];
  parts.forEach(function (seg, i) {
    if (i) {
      const dot = document.createElement("span");
      dot.className = "jwt-dot";
      dot.textContent = ".";
      box.appendChild(dot);
    }
    const span = document.createElement("span");
    span.className = cls[i] || "jwt-s";
    span.textContent = seg;
    box.appendChild(span);
  });
  return box;
}

function jwtJsonBlock(title, obj, kind) {
  const wrap = document.createElement("div");
  wrap.className = "jwt-block";
  const h = document.createElement("div");
  h.className = "jwt-block-title " + kind;
  h.textContent = title;
  const pre = document.createElement("pre");
  pre.className = "jwt-json";
  pre.textContent = JSON.stringify(obj, null, 2);
  wrap.appendChild(h);
  wrap.appendChild(pre);
  return wrap;
}

function jwtClaimsBlock(claims) {
  const wrap = document.createElement("div");
  wrap.className = "jwt-block";
  const h = document.createElement("div");
  h.className = "jwt-block-title";
  h.textContent = "Klaim standar";
  wrap.appendChild(h);
  claims.forEach(function (c) {
    const row = document.createElement("div");
    row.className = "jwt-claim";
    const k = document.createElement("span");
    k.className = "jwt-claim-key";
    k.textContent = c.label + " (" + c.key + ")";
    const v = document.createElement("span");
    v.className = "jwt-claim-val";
    v.textContent = c.note ? c.value + " · " + c.note : String(c.value);
    row.appendChild(k);
    row.appendChild(v);
    wrap.appendChild(row);
  });
  return wrap;
}

function jwtVerifyBadge(verify) {
  const badge = document.createElement("div");
  if (verify === null || verify === undefined) {
    badge.className = "jwt-verify none";
    badge.textContent = "Signature belum diverifikasi (isi secret untuk mengecek).";
    return badge;
  }
  badge.className = "jwt-verify " + (verify.verified ? "ok" : "bad");
  badge.textContent = (verify.verified ? "✓ Signature Verified — " : "✗ Invalid Signature — ")
    + verify.reason;
  return badge;
}

async function jwtDecode() {
  const token = jwtToken.value.trim();
  if (!token) { showError("jwt-out", "Token masih kosong."); return; }
  loading("jwt-dec-run", true);
  setOut("jwt-out", "Membaca token...", true);
  try {
    const res = await fetch("/api/jwt/decode", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token: token, secret: jwtSecret.value })
    });
    const data = await res.json();
    if (data.error) { showError("jwt-out", data.error); return; }
    const out = document.getElementById("jwt-out");
    out.classList.remove("empty");
    out.textContent = "";
    out.appendChild(jwtColorToken(token));
    out.appendChild(jwtVerifyBadge(data.verify));
    out.appendChild(jwtJsonBlock("Header", data.header, "jwt-h"));
    out.appendChild(jwtJsonBlock("Payload", data.payload, "jwt-p"));
    if (data.claims && data.claims.length) out.appendChild(jwtClaimsBlock(data.claims));
    document.getElementById("jwt-meta").textContent =
      "alg " + (data.algorithm || "?");
  } catch (e) {
    showError("jwt-out", "Gagal terhubung ke server.");
  } finally {
    loading("jwt-dec-run", false);
  }
}

async function jwtEncode() {
  const payload = document.getElementById("jwt-payload").value.trim();
  const secret = document.getElementById("jwt-enc-secret").value;
  if (!payload) { showError("jwt-out", "Payload JSON masih kosong."); return; }
  if (!secret) { showError("jwt-out", "Secret masih kosong."); return; }
  loading("jwt-enc-run", true);
  setOut("jwt-out", "Menandatangani token...", true);
  try {
    const res = await fetch("/api/jwt/encode", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload: payload, secret: secret, algorithm: jwtAlg() })
    });
    const data = await res.json();
    if (data.error) { showError("jwt-out", data.error); return; }
    const out = document.getElementById("jwt-out");
    out.classList.remove("empty");
    out.textContent = "";
    out.appendChild(jwtColorToken(data.token));
    const actions = document.createElement("div");
    actions.className = "row";
    const copy = document.createElement("button");
    copy.className = "mcopy";
    copy.textContent = "Salin token";
    copy.addEventListener("click", function () { copyText(data.token, copy); });
    const send = document.createElement("button");
    send.className = "msend";
    send.textContent = "→ Decode";
    send.addEventListener("click", function () {
      setJwtMode("decode");
      jwtToken.value = data.token;
      jwtSecret.value = secret;
      jwtDecode();
    });
    actions.appendChild(copy);
    actions.appendChild(send);
    out.appendChild(actions);
    document.getElementById("jwt-meta").textContent = "alg " + data.algorithm;
  } catch (e) {
    showError("jwt-out", "Gagal terhubung ke server.");
  } finally {
    loading("jwt-enc-run", false);
  }
}

updateCounter("ed-input", "ed-count");
updateCounter("ob-input", "ob-count");
updateCounter("st-msg", "st-msg-count");
