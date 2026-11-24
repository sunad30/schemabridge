const $ = (id) => document.getElementById(id);
let current = null;
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function notice(message) {
  $("error").textContent = message;
  $("error").classList.toggle("hidden", !message);
}
async function api(path, options = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!r.ok) {
    const j = await r.json();
    throw new Error(
      typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail),
    );
  }
  return r.json();
}
async function busy(button, fn) {
  notice("");
  button.disabled = true;
  const old = Array.from(button.childNodes).map((node) => node.cloneNode(true));
  button.textContent = "Working…";
  try {
    await fn();
  } catch (e) {
    notice(e.message);
  } finally {
    button.disabled = false;
    button.replaceChildren(...old);
  }
}
async function history() {
  const runs = await api("/api/runs");
  $("history").replaceChildren();
  if (!runs.length) $("history").append(el("p", "No saved runs yet."));
  for (const run of runs) {
    const b = el("button", run.id.slice(0, 8));
    b.append(el("small", new Date(run.created).toLocaleString()));
    b.onclick = () =>
      busy(b, async () => {
        current = await api("/api/runs/" + run.id);
        render();
      });
    $("history").append(b);
  }
}
function stat(label, value) {
  const d = el("div", undefined, "stat");
  d.append(el("div", label, "label"), el("div", String(value), "number"));
  return d;
}
function download(path) {
  const a = el("a");
  a.href = path;
  a.download = "";
  document.body.append(a);
  a.click();
  a.remove();
}
function audit() {
  const box = $("audit");
  box.replaceChildren();
  for (const e of current.events)
    box.append(
      el("div", e.kind + " · " + new Date(e.created).toLocaleString(), "trace"),
    );
}
let schema = {};
function render() {
  $("empty").classList.add("hidden");
  $("result").classList.remove("hidden");
  $("stats").replaceChildren(
    stat("Source rows", current.rows.length),
    stat("Columns", current.headers.length),
    stat("Needs mapping", current.suggestions.filter((s) => !s.target).length),
  );
  $("model").textContent = current.model_version;
  $("mappings").replaceChildren();
  for (const suggestion of current.suggestions) {
    const tr = el("tr");
    const source = el("td", suggestion.source);
    source.append(el("small", suggestion.samples.join(" · ")));
    const cell = el("td");
    const select = el("select");
    select.dataset.source = suggestion.source;
    select.setAttribute("aria-label", "Map " + suggestion.source);
    select.append(new Option("Ignore / unmapped", ""));
    for (const [key, v] of Object.entries(schema))
      select.append(new Option(key + (v.required ? " *" : ""), key));
    select.value =
      (current.mapping
        ? current.mapping[suggestion.source]
        : suggestion.target) || "";
    cell.append(select);
    const score = el(
      "td",
      Math.round(suggestion.candidates[0].score * 100) + "%",
    );
    score.append(
      el(
        "small",
        suggestion.candidates
          .map((c) => c.field + " " + Math.round(c.score * 100) + "%")
          .join(" · "),
      ),
    );
    score.append(
      el(
        "small",
        "Value compatibility: " +
          suggestion.candidates
            .map(
              (c) =>
                c.field +
                " " +
                Math.round(suggestion.profile[c.field] * 100) +
                "%",
            )
            .join(" · "),
      ),
    );
    tr.append(source, cell, score);
    $("mappings").append(tr);
  }
  $("hash").textContent =
    "Input SHA-256: " + current.source_hash + " · Version " + current.version;
  audit();
  $("validation").classList.toggle("hidden", !current.validation);
  if (current.validation) {
    const v = current.validation;
    $("validation-summary").textContent =
      v.valid_rows.length +
      " valid rows ready to export · " +
      v.invalid_row_count +
      " quarantined rows · " +
      v.ignored_columns.length +
      " ignored columns. Duplicate IDs quarantine every occurrence.";
    $("issues").replaceChildren();
    if (!v.issues.length)
      $("issues").append(
        el("p", "All mapped rows satisfy the contract.", "good"),
      );
    for (const issue of v.issues)
      $("issues").append(
        el(
          "div",
          "Row " + issue.row + " · " + issue.field + " — " + issue.message,
          "issue",
        ),
      );
    $("export").disabled = !v.valid_rows.length;
  }
}
$("sample").onclick = () =>
  busy($("sample"), async () => {
    $("csv").value = (await api("/api/sample")).csv;
  });
$("file").onchange = async () => {
  const f = $("file").files[0];
  if (!f) return;
  if (f.size > 256000) {
    notice("Choose a CSV under 256 KB");
    return;
  }
  $("csv").value = await f.text();
};
$("analyze").onclick = () =>
  busy($("analyze"), async () => {
    current = await api("/api/runs", {
      method: "POST",
      body: JSON.stringify({ csv: $("csv").value }),
    });
    render();
    await history();
  });
$("review").onclick = () =>
  busy($("review"), async () => {
    const mapping = Object.create(null);
    for (const s of $("mappings").querySelectorAll("select"))
      mapping[s.dataset.source] = s.value || null;
    current = await api("/api/runs/" + current.id + "/review", {
      method: "POST",
      body: JSON.stringify({ version: current.version, mapping }),
    });
    render();
    await history();
  });
$("export").onclick = () => download("/api/runs/" + current.id + "/export");
(async () => {
  try {
    schema = await api("/api/schema");
    await history();
  } catch (e) {
    notice(e.message);
  }
})();
