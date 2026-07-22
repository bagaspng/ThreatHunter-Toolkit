const $ = (id) => document.getElementById(id);

$("in").addEventListener("input", () => {
  $("count").textContent = $("in").value.length + " karakter";
});

$("clear").addEventListener("click", () => {
  $("in").value = ""; $("fname").textContent = ""; $("file").value = "";
  $("count").textContent = "0 karakter"; $("verdict-card").hidden = true;
});

$("file").addEventListener("change", () => {
  const f = $("file").files[0];
  $("fname").textContent = f ? f.name : "";
});

$("run").addEventListener("click", analyze);

async function analyze() {
  const file = $("file").files[0];
  let resp;
  if (file) {
    const fd = new FormData();
    fd.append("file", file);
    resp = await fetch("/api/analyze", { method: "POST", body: fd });
  } else {
    resp = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("in").value }),
    });
  }
  const data = await resp.json();
  render(data);
}

function render(data) {
  const card = $("verdict-card");
  card.hidden = false;
  const v = $("verdict");
  if (data.error) {
    v.className = "verdict yes";
    v.textContent = "Error: " + data.error;
    $("findings").innerHTML = "";
    return;
  }
  const yes = data.verdict.obfuscated;
  v.className = "verdict " + (yes ? "yes" : "no");
  v.textContent = yes
    ? `OBFUSCATED — dominan: ${data.verdict.dominant} (${data.verdict.score}%)`
    : "Bersih — tidak ada tanda obfuscate kuat.";

  $("findings").innerHTML = data.findings.map((f) => `
    <div class="finding">
      <div><span class="fname">${escapeHtml(f.name)}</span><span class="tag">${escapeHtml(f.category)}</span></div>
      <div class="bar"><span style="width:${Number(f.confidence)||0}%"></span></div>
      <div class="evidence">Bukti: ${escapeHtml(f.evidence)}</div>
      <div class="clue">Clue: ${escapeHtml(f.clue)}</div>
    </div>`).join("");
}

function escapeHtml(s) {
  return s.replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
