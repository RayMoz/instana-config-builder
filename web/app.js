"use strict";
let CAT = [],
  CATS = [],
  BYKEY = {},
  INFO = {};
const $ = (id) => document.getElementById(id);
const S = { order: [], plugins: {}, comments: false, file: "", uploadName: "", collapsed: {} };
const store = {
  get() {
    try {
      return JSON.parse(localStorage.getItem("icb-state") || "null");
    } catch (e) {
      return null;
    }
  },
  set(v) {
    try {
      localStorage.setItem("icb-state", JSON.stringify(v));
    } catch (e) {}
  },
};
let filterMode = "all",
  sugN = 0,
  savedText = null;

function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  if (attrs)
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k === "text") e.textContent = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else e.setAttribute(k, v === true ? "" : v);
    }
  for (const c of kids.flat()) {
    if (c == null) continue;
    e.append(c.nodeType ? c : document.createTextNode(c));
  }
  return e;
}

/* ---------------- YAML-Erzeugung ---------------- */
const q = (s) => "'" + String(s).replace(/'/g, "''") + "'";
const qk = (k) => (/^[A-Za-z0-9_][A-Za-z0-9_.\-\/]*$/.test(k) ? k : q(k));
const isNum = (s) => /^-?\d+(\.\d+)?$/.test(String(s).trim());
function scalar(v, hint) {
  const s = String(v).trim();
  if (hint === "bool" || s === "true" || s === "false") return s === "true" || s === "false" ? s : q(s);
  if (isNum(s)) return s;
  return q(s);
}
const pad = (n) => " ".repeat(n);
function indentText(t, n) {
  return t
    .replace(/\s+$/, "")
    .split("\n")
    .map((l) => (l.trim() ? pad(n) + l : ""))
    .join("\n");
}
function isRaw(v) {
  return v && typeof v === "object" && !Array.isArray(v) && "$raw" in v;
}
function comment(f, ind, out) {
  if (S.comments && f.d) out.push(pad(ind) + "# " + f.d + (f.u ? " [" + f.u + "]" : ""));
}

function altFor(f, v) {
  if (v == null) return null;
  return (
    f.alts.find((a) =>
      a.t === "list" ? Array.isArray(v) : a.t === "obj" ? typeof v === "object" && !Array.isArray(v) : false,
    ) || null
  );
}
function emitFields(fields, vals, ind, out) {
  for (const f of fields) emitField(f, vals ? vals[f.k] : undefined, ind, out);
}
function emitField(f, v, ind, out) {
  if (v === undefined || v === null) return;
  const key = pad(ind) + qk(f.k) + ":";
  if (isRaw(v)) {
    if (!v.$raw.trim()) return;
    comment(f, ind, out);
    out.push(key);
    out.push(indentText(v.$raw, ind + 2));
    return;
  }
  switch (f.t) {
    case "str":
    case "secret":
    case "enum": {
      if (String(v).trim() === "") return;
      comment(f, ind, out);
      out.push(
        key +
          " " +
          (f.bare && /^[A-Za-z0-9_.\-]+$/.test(String(v).trim()) ? String(v).trim() : q(String(v).trim())),
      );
      return;
    }
    case "int": {
      const s = String(v).trim();
      if (s === "") return;
      comment(f, ind, out);
      out.push(key + " " + (isNum(s) ? s : q(s)));
      return;
    }
    case "bool": {
      if (v !== "true" && v !== "false") return;
      comment(f, ind, out);
      out.push(key + " " + v);
      return;
    }
    case "list": {
      const a = (v || []).map((x) => String(x).trim()).filter(Boolean);
      if (!a.length) return;
      comment(f, ind, out);
      out.push(key);
      a.forEach((x) => out.push(pad(ind + 2) + "- " + (f.bare && /^[A-Za-z0-9_.\-]+$/.test(x) ? x : q(x))));
      return;
    }
    case "kv": {
      const a = (v || []).filter((r) => r[0] && String(r[0]).trim());
      if (!a.length) return;
      comment(f, ind, out);
      out.push(key);
      a.forEach((r) => out.push(pad(ind + 2) + qk(r[0].trim()) + ": " + scalar(r[1] ?? "", f.vt)));
      return;
    }
    case "obj": {
      const sub = [];
      emitFields(f.f, v, ind + 2, sub);
      if (!sub.length) return;
      comment(f, ind, out);
      out.push(key, ...sub);
      return;
    }
    case "objlist": {
      const items = [];
      for (const it of v || []) {
        const sub = [];
        emitFields(f.f, it, ind + 4, sub);
        if (!sub.length) continue;
        const i = sub.findIndex((l) => !l.trimStart().startsWith("#"));
        for (let j = 0; j < i; j++) sub[j] = pad(ind + 2) + sub[j].trimStart();
        sub[i] = pad(ind + 2) + "- " + sub[i].slice(ind + 4);
        items.push(...sub);
      }
      if (!items.length) return;
      comment(f, ind, out);
      out.push(key, ...items);
      return;
    }
    case "map": {
      const items = [];
      for (const it of v || []) {
        if (!it.name || !it.name.trim()) continue;
        const sub = [];
        emitFields(f.f, it.values, ind + 4, sub);
        items.push(pad(ind + 2) + qk(it.name.trim()) + ":" + (sub.length ? "" : " {}"), ...sub);
      }
      if (!items.length) return;
      comment(f, ind, out);
      out.push(key, ...items);
      return;
    }
    case "yaml": {
      if (!String(v).trim()) return;
      comment(f, ind, out);
      out.push(key);
      out.push(indentText(String(v), ind + 2));
      return;
    }
    case "alt": {
      const a = altFor(f, v);
      if (a) emitField({ ...a, k: f.k, d: f.d }, v, ind, out);
      return;
    }
  }
}
function generate() {
  const now = new Date();
  const d = now.toISOString().slice(0, 10);
  const out = [
    "# Instana Agent – configuration.yaml",
    "# Erzeugt mit dem Instana configuration.yaml Builder am " + d,
    "# Änderungen werden vom Agent meist ohne Neustart übernommen (Ausnahmen siehe Doku).",
    "",
  ];
  const warn = [];
  for (const key of S.order) {
    const p = S.plugins[key];
    const c = BYKEY[key] || { name: key, fields: [] };
    const body = [];
    emitFields(c.fields, p.values, 2, body);
    const extra = (p.extra || "").replace(/\s+$/, "");
    if (extra) {
      const emitted = new Set(
        body.filter((l) => /^ {2}[^ #-]/.test(l)).map((l) => l.trim().split(":")[0].replace(/^'|'$/g, "")),
      );
      const ek = extra
        .split("\n")
        .filter((l) => /^[^ #-][^:]*:/.test(l))
        .map((l) => l.split(":")[0].trim().replace(/^'|'$/g, ""));
      ek.filter((k) => emitted.has(k)).forEach((k) =>
        warn.push(key + ": „" + k + "“ steht im Formular und im zusätzlichen YAML."),
      );
      body.push(indentText(extra, 2));
    }
    out.push("# " + c.name + (c.doc ? " – " + c.doc : ""));
    if (!body.length) {
      out.push(key + ":", pad(2) + "# noch keine Werte gesetzt", "");
      warn.push(c.name + ": noch keine Werte gesetzt (der Abschnitt bleibt leer).");
      continue;
    }
    out.push(key + ":", ...body, "");
  }
  for (const key of S.order)
    collectIntWarnings(BYKEY[key]?.fields || [], S.plugins[key].values, (BYKEY[key] || {}).name || key, warn);
  return { text: out.join("\n").replace(/\n+$/, "\n"), warn };
}
function collectIntWarnings(fields, vals, where, warn) {
  if (!vals) return;
  for (const f of fields) {
    const v = vals[f.k];
    if (v == null || isRaw(v)) continue;
    if (f.t === "int" && String(v).trim() && !isNum(v))
      warn.push(where + ": „" + f.k + "“ erwartet eine Zahl.");
    if (f.t === "obj") collectIntWarnings(f.f, v, where, warn);
    if (f.t === "alt") {
      const a = altFor(f, v);
      if (a && a.t === "obj") collectIntWarnings(a.f, v, where, warn);
    }
    if (f.t === "objlist") (v || []).forEach((it) => collectIntWarnings(f.f, it, where, warn));
    if (f.t === "map") (v || []).forEach((it) => collectIntWarnings(f.f, it.values, where, warn));
  }
}

function highlight(t) {
  return t
    .split("\n")
    .map((l) => {
      const e = l.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      if (/^\s*#/.test(l)) return '<span class="yc">' + e + "</span>";
      return e
        .replace(/^(\s*-?\s*)([^:'"]+?)(:)(?=\s|$)/, '$1<span class="yk">$2</span>$3')
        .replace(/('(?:[^']|'')*')/g, '<span class="ys">$1</span>');
    })
    .join("\n");
}

let lastText = "";
function refresh() {
  const { text, warn } = generate();
  lastText = text;
  $("yaml").innerHTML = highlight(text);
  if (!S.order.length)
    setStatus("info", "Links Plugins auswählen. Die Vorschau aktualisiert sich beim Tippen.");
  else if (warn.length) setStatus("warn", warn.join(" · "));
  else setStatus("info", S.order.length + " Abschnitt(e). „Prüfen“ testet die YAML-Syntax.");
  persist();
}
function setStatus(kind, msg) {
  const s = $("status");
  s.className = "status " + kind;
  s.textContent = msg;
}
function persist() {
  store.set(S);
  $("dirty").hidden = savedText === null ? !S.order.length : lastText === savedText;
}
function setFile(p) {
  S.file = p || "";
  const cf = $("curfile");
  cf.innerHTML = "";
  cf.title = S.file;
  if (S.file) {
    const i = Math.max(S.file.lastIndexOf("/"), S.file.lastIndexOf("\\"));
    cf.append(
      el("b", { text: S.file.slice(i + 1) }),
      el("span", { class: "cfdir", text: S.file.slice(0, i) }),
    );
  } else cf.append("(noch nicht gespeichert)");
  document.title = (S.file ? S.file.split(/[\\/]/).pop() + " – " : "") + "Instana configuration.yaml Builder";
}

/* ---------------- Katalog ---------------- */
function renderCatalog() {
  const term = $("q").value.trim().toLowerCase();
  const groups = {};
  for (const c of CAT) {
    if (filterMode === "doc" && !c.fields.length) continue;
    if (filterMode === "sel" && !term && !S.plugins[c.key]) continue;
    if (term && !(c.name + " " + c.key + " " + c.cat).toLowerCase().includes(term)) continue;
    (groups[c.cat] = groups[c.cat] || []).push(c);
  }
  const custom = S.order.filter((k) => !BYKEY[k] || BYKEY[k].custom);
  const box = $("cats");
  box.innerHTML = "";
  const order = [...CATS, "Eigene"];
  if (custom.length && filterMode !== "doc")
    groups["Eigene"] = custom
      .filter((k) => !term || k.toLowerCase().includes(term))
      .map((k) => ({ key: k, name: k, fields: [], src: "custom" }));
  const cats = Object.keys(groups).sort(
    (a, b) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99),
  );
  if (!cats.length) {
    box.append(
      el(
        "p",
        { class: "note" },
        "Kein Plugin passt zur Suche. Unten lässt sich jeder Schlüssel frei hinzufügen.",
      ),
    );
    return;
  }
  for (const cat of cats) {
    const sec = el("div", { class: "cat" }, el("h3", { text: cat }));
    for (const c of groups[cat]) {
      const on = !!S.plugins[c.key];
      sec.append(
        el(
          "button",
          { class: "pl", "aria-pressed": String(on), title: c.key, onclick: () => togglePlugin(c.key) },
          el("span", { class: "box" }),
          el(
            "span",
            null,
            el("span", { class: "nm", text: c.name }),
            el("span", { class: "k", text: c.key }),
          ),
          c.fields.length
            ? el("span", { class: "tag doc", text: c.fields.length + " Opt." })
            : el("span", { class: "tag", text: "frei" }),
        ),
      );
    }
    box.append(sec);
  }
}
function togglePlugin(key) {
  if (S.plugins[key]) removePlugin(key);
  else addPlugin(key);
}
function addPlugin(key, values, extra) {
  if (!S.plugins[key]) {
    S.plugins[key] = { key, values: values || {}, extra: extra || "" };
    S.order.push(key);
  }
  delete S.collapsed[key];
  renderCatalog();
  renderEditor();
  refresh();
  const card = document.getElementById("card-" + cssId(key));
  if (card) card.scrollIntoView({ behavior: "smooth", block: "nearest" });
}
function removePlugin(key) {
  delete S.plugins[key];
  delete S.collapsed[key];
  S.order = S.order.filter((k) => k !== key);
  renderCatalog();
  renderEditor();
  refresh();
}
const cssId = (k) => k.replace(/[^A-Za-z0-9_-]/g, "_");

/* ---------------- Editor ---------------- */
function renderEditor() {
  const ed = $("editor");
  ed.innerHTML = "";
  if (!S.order.length) {
    ed.append(
      el(
        "div",
        { class: "empty" },
        el("p", null, el("b", null, "Noch keine Plugins ausgewählt.")),
        el(
          "p",
          null,
          "Wähle links die Sensoren, die du konfigurieren willst. Plugins mit „Opt.“ haben ein Formular mit den Optionen aus der IBM-Doku; bei „frei“ trägst du YAML direkt ein.",
        ),
      ),
    );
    return;
  }
  const setAll = (v) => {
    S.collapsed = {};
    if (v) S.order.forEach((k) => (S.collapsed[k] = true));
    renderEditor();
    persist();
  };
  ed.append(
    el(
      "div",
      { class: "edbar" },
      el("span", { class: "lbl" }, S.order.length + " Abschnitt(e)"),
      el("span", { class: "sp" }),
      el("button", { type: "button", class: "btn small", onclick: () => setAll(true) }, "Alle einklappen"),
      el("button", { type: "button", class: "btn small", onclick: () => setAll(false) }, "Alle ausklappen"),
    ),
  );
  S.order.forEach((key, idx) => ed.append(renderCard(key, idx)));
}
/* Pfeil-Symbol für die Umschaltfläche (zeigt nach unten = ausgeklappt) */
function chevron() {
  const s = el("span", { class: "chev", "aria-hidden": "true" });
  s.innerHTML =
    '<svg viewBox="0 0 16 16" width="14" height="14"><path d="M3.5 6 8 10.5 12.5 6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  return s;
}
/* Anzahl gesetzter Werte – wird im eingeklappten Zustand angezeigt */
function countSet(p, c) {
  let n = c.fields.filter((f) => hasValue(p.values[f.k])).length;
  if ((p.extra || "").trim()) n++;
  return n;
}
function renderCard(key, idx) {
  const p = S.plugins[key];
  const c = BYKEY[key] || { key, name: key, fields: [], src: "custom" };
  const collapsed = !!S.collapsed[key];
  const card = el("article", {
    class: "card" + (collapsed ? " collapsed" : ""),
    id: "card-" + cssId(key),
  });
  const rerender = () => {
    card.replaceWith(renderCard(key, S.order.indexOf(key)));
    refresh();
  };
  const bdId = "bd-" + cssId(key);
  const toggle = () => {
    if (S.collapsed[key]) delete S.collapsed[key];
    else S.collapsed[key] = true;
    card.replaceWith(renderCard(key, S.order.indexOf(key)));
    persist();
  };
  const n = collapsed ? countSet(p, c) : 0;
  card.append(
    el(
      "div",
      {
        class: "hd",
        title: collapsed ? "Klicken zum Ausklappen" : "Klicken zum Einklappen",
        // Klick auf eine freie Stelle der Kopfzeile klappt um; Schaltflächen und Links behalten ihre Funktion
        onclick: (e) => {
          if (!e.target.closest("button, a, input, select, textarea")) toggle();
        },
      },
      el(
        "button",
        {
          type: "button",
          class: "chevbtn",
          "aria-expanded": String(!collapsed),
          "aria-controls": bdId,
          "aria-label": (collapsed ? "Ausklappen: " : "Einklappen: ") + c.name,
          onclick: toggle,
        },
        chevron(),
      ),
      el("h2", { text: c.name }),
      el("code", { text: key }),
      collapsed
        ? el("span", { class: "tag" + (n ? " doc" : "") }, n ? n + " gesetzt" : "leer")
        : null,
      el("span", { class: "sp" }),
      c.doc ? el("a", { href: c.doc, target: "_blank", rel: "noopener" }, "Doku") : null,
      el(
        "button",
        { class: "btn small", title: "Nach oben", disabled: idx === 0, onclick: () => move(key, -1) },
        "↑",
      ),
      el(
        "button",
        {
          class: "btn small",
          title: "Nach unten",
          disabled: idx === S.order.length - 1,
          onclick: () => move(key, 1),
        },
        "↓",
      ),
      el("button", { class: "btn small danger", onclick: () => removePlugin(key) }, "Entfernen"),
    ),
  );
  if (collapsed) {
    card.append(el("div", { class: "bd", id: bdId, hidden: true }));
    return card;
  }
  const bd = el("div", { class: "bd", id: bdId });
  if (c.note) bd.append(el("div", { class: "note" }, c.note));
  if (c.src === "agent-template")
    bd.append(
      el(
        "div",
        { class: "note" },
        "Optionen aus der Beispielkonfiguration des Agents. Neuere Sensorversionen kennen evtl. weitere Schlüssel – die lassen sich unten als zusätzliches YAML ergänzen.",
      ),
    );
  if (!c.fields.length)
    bd.append(
      el(
        "div",
        { class: "note" },
        c.src === "custom"
          ? "Eigener Schlüssel – Inhalt als YAML eintragen."
          : "Für dieses Plugin sind keine Optionen im Katalog hinterlegt. Trage die Konfiguration aus der Doku als YAML ein.",
      ),
    );
  const osList = [...new Set(c.fields.flatMap((f) => f.os || []))];
  const view = osList.length ? (S.osView && S.osView[key]) || "all" : "all";
  if (osList.length) {
    const bar = el("div", {
      class: "osbar",
      role: "radiogroup",
      "aria-label": "Optionen für Betriebssystem",
    });
    bar.append(el("span", { class: "lbl" }, "Optionen für"));
    for (const o of ["all", ...osList]) {
      bar.append(
        el(
          "button",
          {
            type: "button",
            class: "chip",
            role: "radio",
            "aria-pressed": String(view === o),
            "aria-checked": String(view === o),
            onclick: () => {
              S.osView = S.osView || {};
              S.osView[key] = o;
              rerender();
            },
          },
          o === "all" ? "Alle" : OS_LABEL[o] || o,
        ),
      );
    }
    bd.append(bar);
  }
  let hidden = 0;
  for (const f of c.fields) {
    const show = view === "all" || !f.os || f.os.includes(view) || hasValue(p.values[f.k]);
    if (show) bd.append(renderField(f, p.values, rerender));
    else hidden++;
  }
  if (hidden)
    bd.append(
      el(
        "div",
        { class: "note" },
        hidden +
          " Option(en) für andere Betriebssysteme ausgeblendet. Gesetzte Werte bleiben immer sichtbar.",
      ),
    );
  const ta = el("textarea", {
    class: "inp",
    rows: c.fields.length ? 3 : 6,
    spellcheck: "false",
    placeholder:
      "weitere_option: wert\n# wird unter " + key + " eingefügt (2 Leerzeichen Einrückung automatisch)",
  });
  ta.value = p.extra || "";
  ta.addEventListener("input", () => {
    p.extra = ta.value;
    refresh();
  });
  const det = el(
    "details",
    { class: "extra", open: !c.fields.length || p.extra ? true : null },
    el("summary", null, c.fields.length ? "Zusätzliches YAML" : "YAML"),
    ta,
  );
  bd.append(det);
  card.append(bd);
  return card;
}
function move(key, d) {
  const i = S.order.indexOf(key),
    j = i + d;
  if (j < 0 || j >= S.order.length) return;
  [S.order[i], S.order[j]] = [S.order[j], S.order[i]];
  renderEditor();
  refresh();
}

const OS_LABEL = {
  linux: "Linux",
  aix: "AIX",
  windows: "Windows",
  solaris: "Solaris",
  macos: "macOS",
  ibmi: "IBM i",
  zos: "z/OS",
};
function hasValue(v) {
  if (v == null || v === "") return false;
  if (Array.isArray(v)) return v.length > 0;
  if (typeof v === "object" && !isRaw(v)) return Object.values(v).some(hasValue);
  return true;
}
function label(f) {
  const dv =
    f.def !== undefined
      ? el("span", { class: "dv" }, "Standard: ", el("code", { text: String(f.def) }))
      : null;
  return el(
    "div",
    { class: "lab" },
    el("b", { text: f.k }),
    f.u ? el("span", { class: "u", text: "[" + f.u + "]" }) : null,
    ...(f.os || []).map((o) => el("span", { class: "osb", text: OS_LABEL[o] || o })),
    f.d ? el("span", { class: "d", text: f.d }) : null,
    dv,
  );
}
function renderField(f, container, rerender) {
  const wrap = el("div", { class: "field" });
  wrap.append(label(f));
  const v = container[f.k];
  const complex = ["list", "kv", "obj", "objlist", "map"].includes(f.t);
  if (["kv", "obj", "objlist", "map"].includes(f.t) || f.t === "yaml") wrap.classList.add("wide");
  if (isRaw(v)) {
    const ta = el("textarea", {
      class: "inp set",
      rows: Math.min(14, Math.max(3, v.$raw.split("\n").length + 1)),
      spellcheck: "false",
    });
    ta.value = v.$raw;
    ta.addEventListener("input", () => {
      v.$raw = ta.value;
      refresh();
    });
    wrap.append(
      el(
        "div",
        null,
        ta,
        el(
          "div",
          { class: "ctl" },
          el(
            "span",
            { class: "opt" },
            "Als YAML bearbeitet (z. B. nach Import mit unbekannten Unterschlüsseln).",
          ),
          el(
            "button",
            {
              class: "btn link",
              onclick: () => {
                if (confirm("YAML verwerfen und zum Formular zurückkehren?")) {
                  delete container[f.k];
                  rerender();
                }
              },
            },
            "Zum Formular",
          ),
        ),
      ),
    );
    return wrap;
  }
  const box = el("div");
  const set = (val) => {
    container[f.k] = val;
    refresh();
  };
  if (f.t === "alt") {
    const cur = altFor(f, v) || f.alts[0];
    const sw = el("div", { class: "ctl altsw", role: "radiogroup", "aria-label": "Form" });
    f.alts.forEach((a, ix) => {
      const id = "alt-" + ++sugN;
      const r = el("input", {
        type: "radio",
        name: "alt-" + f.k + "-" + sugN,
        id,
        checked: a === cur ? true : null,
      });
      r.onchange = () => {
        const has = v != null && (Array.isArray(v) ? v.length : Object.keys(v).length);
        if (has && !confirm("Eingaben verwerfen und Form wechseln?")) {
          rerender();
          return;
        }
        container[f.k] = a.t === "list" ? [] : {};
        rerender();
      };
      sw.append(el("label", { class: "opt", for: id }, r, a.label));
    });
    if (container[f.k] == null) container[f.k] = cur.t === "list" ? [] : {};
    const inner = renderField({ ...cur, k: f.k, d: cur.d || "" }, container, rerender);
    inner.querySelector(".lab").remove();
    inner.classList.add("wide");
    box.append(sw, inner);
    wrap.classList.add("wide");
    wrap.append(box);
    return wrap;
  }
  switch (f.t) {
    case "str":
    case "int": {
      const lid = f.sug ? "sug-" + f.k + "-" + ++sugN : null;
      const i = el("input", {
        class: "inp" + (v ? " set" : ""),
        type: "text",
        inputmode: f.t === "int" ? "numeric" : null,
        placeholder: f.ph || (f.def !== undefined ? String(f.def) : ""),
        spellcheck: "false",
        list: lid,
      });
      i.value = v ?? "";
      i.addEventListener("input", () => {
        i.classList.toggle("set", !!i.value);
        set(i.value);
      });
      box.append(i);
      if (lid) {
        const dl = el("datalist", { id: lid });
        f.sug.forEach((o) => dl.append(el("option", { value: o })));
        box.append(dl);
      }
      break;
    }
    case "secret": {
      const i = el("input", {
        class: "inp" + (v ? " set" : ""),
        type: "password",
        autocomplete: "off",
        placeholder: f.ph || "",
      });
      i.value = v ?? "";
      i.addEventListener("input", () => {
        i.classList.toggle("set", !!i.value);
        set(i.value);
      });
      const b = el(
        "button",
        {
          class: "btn small",
          type: "button",
          onclick: () => {
            i.type = i.type === "password" ? "text" : "password";
            b.textContent = i.type === "password" ? "Zeigen" : "Verbergen";
          },
        },
        "Zeigen",
      );
      box.append(el("div", { class: "secret" }, i, b));
      break;
    }
    case "bool": {
      const s = el("select", { class: "inp" + (v ? " set" : "") });
      [
        ["", "– nicht setzen –"],
        ["true", "true"],
        ["false", "false"],
      ].forEach(([a, b]) => s.append(el("option", { value: a, text: b })));
      s.value = v ?? "";
      s.addEventListener("change", () => {
        s.classList.toggle("set", !!s.value);
        set(s.value || undefined);
      });
      box.append(s);
      break;
    }
    case "enum": {
      const s = el("select", { class: "inp" + (v ? " set" : "") });
      s.append(el("option", { value: "", text: "– nicht setzen –" }));
      const opts = [...f.opts];
      if (v && !opts.includes(v)) opts.push(v);
      opts.forEach((o) => s.append(el("option", { value: o, text: o })));
      s.value = v ?? "";
      s.addEventListener("change", () => {
        s.classList.toggle("set", !!s.value);
        set(s.value || undefined);
      });
      box.append(s);
      break;
    }
    case "list": {
      const t = el("textarea", {
        class: "inp" + (v && v.length ? " set" : ""),
        rows: Math.max(2, Math.min(8, (v || []).length + 1)),
        spellcheck: "false",
        placeholder: "ein Eintrag pro Zeile" + (f.ph ? "\nz. B. " + f.ph : ""),
      });
      t.value = (v || []).join("\n");
      t.addEventListener("input", () => {
        t.classList.toggle("set", !!t.value.trim());
        set(
          t.value
            .split("\n")
            .map((x) => x.trim())
            .filter(Boolean),
        );
      });
      box.append(t);
      if (f.ex && !(v && v.length))
        box.append(
          el(
            "div",
            { class: "ctl" },
            el(
              "button",
              {
                class: "btn link",
                onclick: () => {
                  container[f.k] = [...f.ex];
                  rerender();
                },
              },
              "Beispielwerte einsetzen",
            ),
          ),
        );
      break;
    }
    case "kv": {
      const rows = (container[f.k] = v || []);
      const list = el("div");
      rows.forEach((r, i) => {
        const a = el("input", { class: "inp", placeholder: f.kph || "Schlüssel", spellcheck: "false" });
        a.value = r[0] ?? "";
        const b = el("input", {
          class: "inp",
          placeholder: f.vt === "bool" ? "true / false" : "Wert",
          spellcheck: "false",
        });
        b.value = r[1] ?? "";
        a.addEventListener("input", () => {
          r[0] = a.value;
          refresh();
        });
        b.addEventListener("input", () => {
          r[1] = b.value;
          refresh();
        });
        list.append(
          el(
            "div",
            { class: "kvrow" },
            a,
            b,
            el(
              "button",
              {
                class: "btn small",
                title: "Entfernen",
                onclick: () => {
                  rows.splice(i, 1);
                  rerender();
                },
              },
              "×",
            ),
          ),
        );
      });
      box.append(
        list,
        el(
          "div",
          { class: "ctl" },
          el(
            "button",
            {
              class: "btn small",
              onclick: () => {
                rows.push(["", f.vt === "bool" ? "false" : ""]);
                rerender();
              },
            },
            "+ Eintrag",
          ),
        ),
      );
      break;
    }
    case "obj": {
      const sub = (container[f.k] = v || {});
      const n = el("div", { class: "nest" });
      f.f.forEach((sf) => n.append(renderField(sf, sub, rerender)));
      box.append(n);
      break;
    }
    case "objlist": {
      const items = (container[f.k] = v || []);
      const n = el("div", { class: "nest" });
      items.forEach((it, i) => {
        const ib = el(
          "div",
          { class: "item" },
          el(
            "div",
            { class: "ih" },
            el("span", { text: "Eintrag " + (i + 1) }),
            el("span", { class: "sp" }),
            el(
              "button",
              {
                class: "btn small danger",
                onclick: () => {
                  items.splice(i, 1);
                  rerender();
                },
              },
              "Entfernen",
            ),
          ),
        );
        f.f.forEach((sf) => ib.append(renderField(sf, it, rerender)));
        n.append(ib);
      });
      n.append(
        el(
          "div",
          { class: "ctl" },
          el(
            "button",
            {
              class: "btn small",
              onclick: () => {
                items.push({});
                rerender();
              },
            },
            "+ Eintrag",
          ),
        ),
      );
      box.append(n);
      break;
    }
    case "map": {
      const items = (container[f.k] = v || []);
      const n = el("div", { class: "nest" });
      items.forEach((it, i) => {
        const nm = el("input", {
          placeholder: f.kl || "Name",
          spellcheck: "false",
          "aria-label": f.kl || "Name",
        });
        nm.value = it.name || "";
        nm.addEventListener("input", () => {
          it.name = nm.value;
          refresh();
        });
        it.values = it.values || {};
        const ib = el(
          "div",
          { class: "item" },
          el(
            "div",
            { class: "ih" },
            nm,
            el("span", { class: "sp" }),
            el(
              "button",
              {
                class: "btn small danger",
                onclick: () => {
                  items.splice(i, 1);
                  rerender();
                },
              },
              "Entfernen",
            ),
          ),
        );
        f.f.forEach((sf) => ib.append(renderField(sf, it.values, rerender)));
        n.append(ib);
      });
      n.append(
        el(
          "div",
          { class: "ctl" },
          el(
            "button",
            {
              class: "btn small",
              onclick: () => {
                items.push({ name: "", values: {} });
                rerender();
              },
            },
            "+ " + (f.kl || "Eintrag"),
          ),
        ),
      );
      box.append(n);
      break;
    }
    case "yaml": {
      const t = el("textarea", {
        class: "inp" + (v ? " set" : ""),
        rows: Math.max(3, Math.min(12, String(v || f.ex || "").split("\n").length + 1)),
        spellcheck: "false",
        placeholder: f.ex || "",
      });
      t.value = v || "";
      t.addEventListener("input", () => {
        t.classList.toggle("set", !!t.value.trim());
        set(t.value);
      });
      box.append(t);
      if (f.ex && !v)
        box.append(
          el(
            "div",
            { class: "ctl" },
            el(
              "button",
              {
                class: "btn link",
                onclick: () => {
                  container[f.k] = f.ex;
                  rerender();
                },
              },
              "Beispiel einsetzen",
            ),
          ),
        );
      break;
    }
  }
  if (complex && !isRaw(v))
    box.append(
      el(
        "div",
        { class: "ctl" },
        el(
          "button",
          {
            class: "btn link",
            title: "Diesen Abschnitt frei als YAML bearbeiten",
            onclick: () => {
              const out = [];
              emitField(f, container[f.k], 0, out);
              const txt = out
                .slice(1)
                .map((l) => l.slice(2))
                .join("\n");
              container[f.k] = { $raw: txt };
              rerender();
            },
          },
          "Als YAML bearbeiten",
        ),
      ),
    );
  wrap.append(box);
  return wrap;
}

/* ---------------- Aktionen ---------------- */
async function api(path, body) {
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json();
}
$("bValidate").onclick = async () => {
  const r = await api("/api/validate", { yaml: lastText });
  setStatus(r.ok === true ? "ok" : r.ok === false ? "bad" : "info", r.message);
};
$("bCopy").onclick = async () => {
  try {
    await navigator.clipboard.writeText(lastText);
    setStatus("ok", "In die Zwischenablage kopiert.");
  } catch (e) {
    const r = document.createRange();
    r.selectNodeContents($("yaml"));
    const s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
    setStatus("info", "Text markiert – mit Cmd/Strg+C kopieren.");
  }
};
$("bDownload").onclick = () => {
  const name = S.file.split(/[\\/]/).pop() || "configuration.yaml";
  const a = el("a", {
    href: URL.createObjectURL(new Blob([lastText], { type: "text/yaml" })),
    download: name,
  });
  document.body.append(a);
  a.click();
  a.remove();
};
$("bNew").onclick = () => {
  if (S.order.length && !confirm("Aktuelle Konfiguration verwerfen und neu beginnen?")) return;
  loadState([]);
  setFile("");
  savedText = null;
  refresh();
  setStatus("info", "Neue, leere Konfiguration. Links Plugins auswählen.");
};
$("bSave").onclick = () => {
  if (!S.file) {
    openDialog("save");
    return;
  }
  doSave(S.file, true);
};
$("bSaveAs").onclick = () => openDialog("save");
$("bOpen").onclick = () => openDialog("open");
async function doSave(path, overwrite) {
  const r = await api("/api/save", { yaml: lastText, path, overwrite, backup: $("dBak").checked });
  if (r.ok) {
    setFile(r.path);
    savedText = lastText;
    persist();
    setStatus("ok", r.message);
  } else if (!r.exists) setStatus("bad", r.message);
  return r;
}
function openResult(r, label) {
  if (!r.ok) {
    setStatus("bad", r.message);
    return false;
  }
  loadState(r.plugins);
  const known = r.plugins.filter((p) => BYKEY[p.key] && !BYKEY[p.key].custom).length;
  const names = r.plugins.map((p) => (BYKEY[p.key] && BYKEY[p.key].name) || p.key);
  setStatus(
    r.warnings && r.warnings.length ? "warn" : "ok",
    label +
      ": " +
      r.plugins.length +
      " Abschnitt(e) eingelesen (" +
      known +
      " aus dem Katalog" +
      (r.plugins.length - known ? ", " + (r.plugins.length - known) + " eigene" : "") +
      "): " +
      names.join(", ") +
      (r.warnings && r.warnings.length ? " · " + r.warnings.join(" · ") : ""),
  );
  filterMode = "sel";
  document
    .querySelectorAll(".chip")
    .forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.f === "sel")));
  renderCatalog();
  return true;
}
async function importText(text, name) {
  if (
    S.order.length &&
    lastText !== savedText &&
    !confirm("Ungespeicherte Änderungen verwerfen und „" + name + "“ einlesen?")
  )
    return false;
  const r = await api("/api/import", { yaml: text });
  if (openResult(r, "„" + name + "“")) {
    setFile("");
    savedText = null;
    S.uploadName = name;
    persist();
    setStatus(
      $("status").className.includes("warn") ? "warn" : "ok",
      $("status").textContent + " · Hochgeladene Datei: beim Speichern Ort und Namen wählen.",
    );
    return true;
  }
  return false;
}
$("file").onchange = async (e) => {
  const f = e.target.files[0];
  e.target.value = "";
  if (!f) return;
  if (await importText(await f.text(), f.name)) $("dlg").close();
};
/* Drag & Drop */
let dragN = 0;
window.addEventListener("dragenter", (e) => {
  if ([...e.dataTransfer.types].includes("Files")) {
    dragN++;
    $("drop").hidden = false;
  }
});
window.addEventListener("dragleave", () => {
  if (--dragN <= 0) {
    dragN = 0;
    $("drop").hidden = true;
  }
});
window.addEventListener("dragover", (e) => e.preventDefault());
window.addEventListener("drop", async (e) => {
  e.preventDefault();
  dragN = 0;
  $("drop").hidden = true;
  const f = e.dataTransfer.files[0];
  if (f) await importText(await f.text(), f.name);
});

/* Datei-Dialog */
const D = { mode: "open", dir: "", sel: null, confirmOverwrite: null };
function openDialog(mode) {
  D.mode = mode;
  D.confirmOverwrite = null;
  D.sel = null;
  $("dlgTitle").textContent = mode === "open" ? "Datei öffnen" : "Speichern unter";
  $("dOk").textContent = mode === "open" ? "Öffnen" : "Speichern";
  $("dUpload").hidden = mode !== "open";
  $("dBakWrap").hidden = mode === "open";
  $("dNameLbl").textContent = mode === "open" ? "Datei" : "Dateiname";
  const cur = S.file || INFO.output;
  const sep = INFO.sep || "/";
  const dir = cur.slice(0, cur.lastIndexOf(sep)) || sep;
  $("dName").value =
    mode === "open"
      ? ""
      : S.file
        ? cur.slice(cur.lastIndexOf(sep) + 1)
        : S.uploadName || cur.slice(cur.lastIndexOf(sep) + 1);
  dmsg("");
  loadDir(D.dir || dir);
  $("dlg").showModal();
  setTimeout(() => $(mode === "open" ? "dDir" : "dName").focus(), 30);
}
function dmsg(t, kind) {
  const m = $("dMsg");
  m.hidden = !t;
  m.textContent = t || "";
  m.style.background = kind === "bad" ? "var(--bad-bg)" : "";
  m.style.color = kind === "bad" ? "var(--bad)" : "";
}
async function loadDir(d) {
  const r = await (await fetch("/api/ls?dir=" + encodeURIComponent(d))).json();
  D.dir = r.dir;
  D.parent = r.parent;
  $("dDir").value = r.dir;
  const L = $("dList");
  L.innerHTML = "";
  if (r.error) {
    L.append(el("div", { class: "none" }, "Kein Zugriff: " + r.error));
    return;
  }
  if (!r.entries.length)
    L.append(el("div", { class: "none" }, "Keine Unterordner oder YAML-Dateien in diesem Verzeichnis."));
  for (const e of r.entries) {
    const b = el(
      "button",
      { type: "button", role: "option", "aria-selected": "false" },
      el("span", { class: "ic", text: e.type === "dir" ? "📁" : "📄" }),
      el("span", { text: e.name }),
      el("span", { class: "meta", text: e.type === "dir" ? "" : e.mtime + " · " + fmtSize(e.size) }),
    );
    b.onclick = () => {
      if (e.type === "dir") {
        loadDir(join(r.dir, e.name));
        return;
      }
      L.querySelectorAll("button").forEach((x) => x.setAttribute("aria-selected", "false"));
      b.setAttribute("aria-selected", "true");
      $("dName").value = e.name;
      D.confirmOverwrite = null;
      dmsg("");
    };
    b.ondblclick = () => {
      if (e.type === "file") {
        $("dName").value = e.name;
        dialogOk();
      }
    };
    L.append(b);
  }
}
const fmtSize = (n) => (n < 1024 ? n + " B" : (n / 1024).toFixed(1) + " KB");
const join = (d, n) => (d.endsWith(INFO.sep) ? d + n : d + INFO.sep + n);
$("dUp").onclick = () => {
  if (D.parent) loadDir(D.parent);
};
$("dHome").onclick = () => loadDir(INFO.home);
$("dGo").onclick = () => loadDir($("dDir").value);
$("dDir").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    loadDir($("dDir").value);
  }
});
$("dName").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    dialogOk();
  }
});
$("dName").addEventListener("input", () => {
  D.confirmOverwrite = null;
  dmsg("");
});
$("dUpload").onclick = () => $("file").click();
$("dOk").onclick = () => dialogOk();
async function dialogOk() {
  let name = $("dName").value.trim();
  if (!name) {
    dmsg(D.mode === "open" ? "Bitte eine Datei auswählen." : "Bitte einen Dateinamen eingeben.", "bad");
    return;
  }
  const path = /^([\/~]|[A-Za-z]:)/.test(name) ? name : join(D.dir, name);
  if (D.mode === "open") {
    if (S.order.length && lastText !== savedText && !confirm("Ungespeicherte Änderungen verwerfen?")) return;
    const r = await api("/api/open", { path });
    if (!r.ok) {
      dmsg(r.message, "bad");
      return;
    }
    setFile(r.path);
    savedText = null;
    S.uploadName = "";
    openResult(r, r.path.split(/[\\/]/).pop());
    savedText = lastText;
    persist();
    $("dlg").close();
    return;
  }
  if (!/\.ya?ml$/i.test(name) && !D.confirmOverwrite) {
    /* Endung ergänzen */ name += ".yaml";
    $("dName").value = name;
    return dialogOk();
  }
  const r = await doSave(path, D.confirmOverwrite === path);
  if (r.ok) {
    S.uploadName = "";
    $("dlg").close();
    return;
  }
  if (r.exists) {
    D.confirmOverwrite = path;
    dmsg(
      "„" +
        name +
        "“ existiert bereits. Nochmals auf „Überschreiben“ klicken, um die Datei zu ersetzen" +
        ($("dBak").checked ? " (eine .bak-Sicherung wird angelegt)." : "."),
    );
    $("dOk").textContent = "Überschreiben";
    return;
  }
  dmsg(r.message, "bad");
}
$("dlg").addEventListener("close", () => {
  $("dOk").textContent = D.mode === "open" ? "Öffnen" : "Speichern";
});

/* Konfigurations-Repository */
const R = { timer: null, target: null, confirm: false };
function rmsg(t, kind) {
  const m = $("rMsg");
  m.hidden = !t;
  m.textContent = t || "";
  m.style.background = kind === "bad" ? "var(--bad-bg)" : "";
  m.style.color = kind === "bad" ? "var(--bad)" : "";
}
async function repoPreview() {
  R.confirm = false;
  $("rOk").textContent = "Speichern";
  const r = await api("/api/repo/target", {
    yaml: lastText,
    pattern: $("rPattern").value,
    name: $("rName").value,
  });
  R.target = r.ok ? r : null;
  if (!r.ok) {
    $("rRel").textContent = "–";
    $("rState").textContent = "";
    rmsg(r.message, "bad");
    return;
  }
  $("rRel").textContent = r.rel;
  if (!$("rName").value.trim())
    $("rName").placeholder = r.used.name ? r.used.name + " (aus Tags)" : "z. B. availability-zone";
  $("rName").disabled = !/\{name\}/.test($("rPattern").value);
  $("rState").className = "tag" + (r.exists ? " warn" : " doc");
  $("rState").textContent = r.exists ? "existiert bereits" : "neu";
  const T = $("rTags");
  T.innerHTML = "";
  if (!r.tags.length) T.append(el("span", { class: "none", text: "keine – im Abschnitt Host unter tags setzen" }));
  r.tags.forEach((t) => T.append(el("code", { class: "rtag", text: t })));
  if (r.zone) T.append(el("code", { class: "rtag zone", text: "Zone: " + r.zone }));
  const notes = [];
  if (r.missing.length) notes.push("Ohne Wert: " + r.missing.map((m) => "{" + m + "}").join(", ") + ".");
  notes.push(...(r.warnings || []));
  rmsg(notes.join(" "), r.warnings && r.warnings.length ? "bad" : "");
}
function openRepoDialog() {
  if (!S.order.length) {
    setStatus("info", "Die Konfiguration ist leer – zuerst Plugins auswählen.");
    return;
  }
  $("rDir").textContent = INFO.repo.dir;
  $("rPattern").value = INFO.repo.pattern;
  /* Name der zuletzt gespeicherten/geöffneten Datei vorschlagen */
  const m = /(?:^|[\\/])configuration-([^\\/]+)\.ya?ml$/i.exec(S.file || "");
  $("rName").value = m ? m[1] : "";
  rmsg("");
  $("rdlg").showModal();
  repoPreview();
  setTimeout(() => $("rName").focus(), 30);
}
$("bRepo").onclick = openRepoDialog;
for (const id of ["rName", "rPattern"]) {
  $(id).addEventListener("input", () => {
    clearTimeout(R.timer);
    R.timer = setTimeout(repoPreview, 200);
  });
  $(id).addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      $("rOk").click();
    }
  });
}
$("rDefault").onclick = () => {
  $("rPattern").value = INFO.repo.default;
  repoPreview();
};
$("rOk").onclick = async () => {
  if (!R.target) return;
  const pattern = $("rPattern").value;
  const r = await api("/api/repo/save", {
    yaml: lastText,
    pattern,
    name: $("rName").value,
    overwrite: R.confirm,
    backup: $("rBak").checked,
  });
  if (r.ok) {
    INFO.repo.pattern = pattern;
    setFile(r.path);
    savedText = lastText;
    S.uploadName = "";
    persist();
    setStatus("ok", "Im Repository gespeichert: " + r.rel + " · „Fleet-Befehle …“ zeigt, wie die Datei verteilt wird.");
    $("rdlg").close();
    return;
  }
  if (r.exists) {
    R.confirm = true;
    rmsg(
      "„" +
        r.rel +
        "“ existiert bereits. Nochmals auf „Überschreiben“ klicken, um die Datei zu ersetzen" +
        ($("rBak").checked ? " (eine .bak-Sicherung wird angelegt)." : "."),
    );
    $("rOk").textContent = "Überschreiben";
    return;
  }
  rmsg(r.message, "bad");
};
$("dRepo").onclick = () => loadDir(INFO.repo.dir);

/* Endgültige Konfiguration: mehrere Dateien wie der Agent zusammenführen */
const M = { dir: "", res: null };
const isAgentName = (n) => /^configuration(-[^\/\\]+)?\.yaml$/.test(n);
const baseName = (p) => p.split(/[\\/]/).pop();
function mergeOrder(paths) {
  /* gleiche Reihenfolge wie icb/merge.py: configuration.yaml zuerst, sonst Zeichencode */
  const key = (p) => (baseName(p) === "configuration.yaml" ? "" : baseName(p));
  return [...paths].sort((a, b) => {
    const ka = key(a), kb = key(b);
    return ka < kb ? -1 : ka > kb ? 1 : a < b ? -1 : a > b ? 1 : 0;
  });
}
function mFiles() {
  return (S.mergeFiles = S.mergeFiles || []);
}
function renderMergeSel() {
  const L = $("mSel");
  L.innerHTML = "";
  const files = mergeOrder(mFiles());
  const seen = {};
  for (const p of files) {
    const n = baseName(p);
    const note = !isAgentName(n)
      ? "wird vom Agenten nicht gelesen"
      : seen[n]
        ? "gleicher Dateiname doppelt"
        : "";
    seen[n] = true;
    const rm = el("button", { type: "button", class: "btn small", title: "Aus der Auswahl entfernen", text: "Entfernen" });
    rm.onclick = () => {
      S.mergeFiles = mFiles().filter((x) => x !== p);
      persist();
      renderMergeSel();
      loadMergeDir(M.dir);
    };
    L.append(
      el(
        "li",
        { class: note ? "bad" : "" },
        el("div", { class: "nm" }, el("strong", { text: n }), note ? el("span", { class: "tag warn", text: note }) : null),
        el("div", { class: "dir", text: "\u200E" + p.slice(0, p.length - n.length - 1) + "\u200E", title: p }),
        rm,
      ),
    );
  }
  if (!files.length) L.append(el("li", { class: "none", text: "Noch keine Dateien ausgewählt – links Dateien anhaken." }));
  $("mCount").textContent = files.length + " Datei(en)";
  $("mRun").disabled = !files.length;
}
async function loadMergeDir(d) {
  const r = await (await fetch("/api/ls?dir=" + encodeURIComponent(d))).json();
  M.dir = r.dir;
  M.parent = r.parent;
  S.mergeDir = r.dir;
  $("mDir").value = r.dir;
  const L = $("mList");
  L.innerHTML = "";
  if (r.error) {
    L.append(el("div", { class: "none" }, "Kein Zugriff: " + r.error));
    return;
  }
  if (!r.entries.length) L.append(el("div", { class: "none" }, "Keine Unterordner oder YAML-Dateien."));
  M.here = [];
  for (const e of r.entries) {
    const full = join(r.dir, e.name);
    if (e.type === "dir") {
      const b = el("button", { type: "button" }, el("span", { class: "ic", text: "📁" }), el("span", { text: e.name }));
      b.onclick = () => loadMergeDir(full);
      L.append(b);
      continue;
    }
    if (isAgentName(e.name)) M.here.push(full);
    const cb = el("input", { type: "checkbox" });
    cb.checked = mFiles().includes(full);
    cb.onchange = () => {
      S.mergeFiles = cb.checked ? [...mFiles(), full] : mFiles().filter((x) => x !== full);
      persist();
      renderMergeSel();
    };
    L.append(
      el(
        "label",
        { class: "mfile" + (isAgentName(e.name) ? "" : " dim"), title: isAgentName(e.name) ? full : "Der Agent liest nur configuration.yaml und configuration-*.yaml" },
        cb,
        el("span", { class: "ic", text: "📄" }),
        el("span", { text: e.name }),
        el("span", { class: "meta", text: e.mtime }),
      ),
    );
  }
  $("mAddAll").disabled = !M.here.length;
}
function openMergeDialog() {
  $("mResult").hidden = true;
  renderMergeSel();
  const start = S.mergeDir || (S.file ? S.file.slice(0, S.file.length - baseName(S.file).length - 1) : INFO.repo.dir);
  loadMergeDir(start);
  $("mdlg").showModal();
}
$("bMerge").onclick = openMergeDialog;
$("mUp").onclick = () => M.parent && loadMergeDir(M.parent);
$("mHome").onclick = () => loadMergeDir(INFO.home);
$("mRepo").onclick = () => loadMergeDir(INFO.repo.dir);
$("mDir").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    loadMergeDir($("mDir").value);
  }
});
$("mAddAll").onclick = () => {
  S.mergeFiles = [...new Set([...mFiles(), ...M.here])];
  persist();
  renderMergeSel();
  loadMergeDir(M.dir);
};
$("mClear").onclick = () => {
  S.mergeFiles = [];
  persist();
  renderMergeSel();
  loadMergeDir(M.dir);
  $("mResult").hidden = true;
};
function showMergeYaml() {
  if (!M.res) return;
  const t = $("mOrigin").checked ? M.res.annotated : M.res.yaml;
  const esc = (x) => x.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  $("mYaml").innerHTML = t
    .split("\n")
    .map((l) => {
      const i = l.lastIndexOf("  # ");
      if (i < 0 || !$("mOrigin").checked) return highlight(l);
      const c = esc(l.slice(i)).replace(/⟵ überschreibt.*/, (x) => '<span class="ovr">' + x + "</span>");
      return highlight(l.slice(0, i)) + '<span class="morig">' + c + "</span>";
    })
    .join("\n");
}
$("mOrigin").onchange = showMergeYaml;
$("mRun").onclick = async () => {
  const r = await api("/api/merge", { paths: mFiles() });
  $("mResult").hidden = false;
  const msg = $("mMsg");
  if (!r.ok) {
    M.res = null;
    msg.hidden = false;
    msg.textContent = r.message;
    $("mConf").innerHTML = "";
    $("mYaml").textContent = "";
    return;
  }
  M.res = r;
  const notes = [...r.warnings];
  r.order.filter((e) => !e.used).forEach((e) => notes.push(e.name + ": " + e.note));
  msg.hidden = !notes.length;
  msg.textContent = notes.join(" · ");
  const C = $("mConf");
  C.innerHTML = "";
  $("mConfN").textContent = String(r.conflicts.length);
  if (!r.conflicts.length) C.append(el("p", { class: "rhelp", text: "Keine Option wird in mehreren Dateien unterschiedlich gesetzt." }));
  else {
    const tb = el("tbody");
    for (const c of r.conflicts) {
      const last = c.steps[c.steps.length - 1];
      tb.append(
        el(
          "tr",
          {},
          el("td", {}, el("code", { text: c.path.join(" › ") })),
          el("td", {}, el("code", { class: "win", text: last.text }), el("div", { class: "src", text: last.file })),
          el(
            "td",
            {},
            ...c.steps.slice(0, -1).map((s) => el("div", { class: "lost" }, el("code", { text: s.text }), " ", el("span", { class: "src", text: s.file }))),
          ),
        ),
      );
    }
    C.append(el("table", { class: "mconf" }, el("thead", {}, el("tr", {}, el("th", { text: "Option" }), el("th", { text: "Endgültiger Wert" }), el("th", { text: "Überschrieben" }))), tb));
  }
  showMergeYaml();
  setTimeout(() => $("mResult").scrollIntoView({ behavior: "smooth", block: "start" }), 30);
};
$("mCopy").onclick = async () => {
  if (!M.res) return;
  try {
    await navigator.clipboard.writeText($("mOrigin").checked ? M.res.annotated : M.res.yaml);
    $("mCopy").textContent = "Kopiert";
    setTimeout(() => ($("mCopy").textContent = "Kopieren"), 1500);
  } catch (e) {
    /* Zwischenablage nicht verfügbar */
  }
};
$("mToEditor").onclick = async () => {
  if (!M.res) return;
  if (await importText(M.res.yaml, "configuration-endgueltig.yaml")) $("mdlg").close();
};

/* Fleet-Befehle (nur anzeigen) */
const F = { timer: null, tags: [], options: [], res: null };
function fleetState() {
  return (S.fleet = S.fleet || { server: "", versions: {} });
}
async function fleetUpdate(first) {
  const st = fleetState();
  const body = { path: S.file, yaml: lastText, server: $("fServer").value };
  if (!first) {
    body.configName = $("fName").value;
    body.version = $("fVer").value;
    body.tags = F.tags;
  } else body.version = st.versions[S.file] || "1.0.0";
  const r = await api("/api/fleet", body);
  F.res = r.ok ? r : null;
  const msg = $("fMsg");
  if (!r.ok) {
    msg.hidden = false;
    msg.textContent = r.message;
    $("fScript").textContent = "";
    return;
  }
  if (first) {
    $("fName").value = r.suggest.configName;
    $("fVer").value = body.version;
    F.tags = [...r.tags];
    F.options = [...r.suggest.selectors];
    renderFleetTags();
  }
  const notes = [...r.warnings];
  if (lastText !== savedText) notes.unshift("Der Editor enthält ungespeicherte Änderungen – hochgeladen wird die gespeicherte Datei.");
  msg.hidden = !notes.length;
  msg.textContent = notes.join(" · ");
  $("fScript").innerHTML = r.script
    .split("\n")
    .map((l) => {
      const e = l.replace(/&/g, "&amp;").replace(/</g, "&lt;");
      return /^\s*#/.test(l) ? '<span class="yc">' + e + "</span>" : e.replace(/(--[a-z-]+)/g, '<span class="yk">$1</span>');
    })
    .join("\n");
}
function renderFleetTags() {
  const T = $("fTags");
  T.innerHTML = "";
  for (const t of [...new Set([...F.options, ...F.tags])]) {
    const cb = el("input", { type: "checkbox" });
    cb.checked = F.tags.includes(t);
    cb.onchange = () => {
      F.tags = cb.checked ? [...F.tags, t] : F.tags.filter((x) => x !== t);
      fleetUpdate();
    };
    T.append(el("label", { class: "rtag fsel" }, cb, " --tag " + t));
  }
  if (!F.options.length && !F.tags.length) T.append(el("span", { class: "none", text: "keine Tags gefunden" }));
}
function openFleetDialog() {
  if (!S.file) {
    setStatus("info", "Bitte die Konfiguration zuerst speichern – am besten „Ins Repository …“.");
    return;
  }
  $("fPath").textContent = S.file;
  $("fServer").value = fleetState().server || "";
  $("fTagAdd").value = "";
  $("fdlg").showModal();
  fleetUpdate(true);
}
$("bFleet").onclick = openFleetDialog;
for (const id of ["fName", "fVer", "fServer"]) {
  $(id).addEventListener("input", () => {
    if (id === "fServer") fleetState().server = $("fServer").value.trim();
    if (id === "fVer") fleetState().versions[S.file] = $("fVer").value.trim();
    persist();
    clearTimeout(F.timer);
    F.timer = setTimeout(() => fleetUpdate(), 200);
  });
}
$("fBump").onclick = () => {
  const m = /^(\d+)\.(\d+)\.(\d+)/.exec($("fVer").value.trim());
  $("fVer").value = m ? m[1] + "." + m[2] + "." + (Number(m[3]) + 1) : "1.0.0";
  fleetState().versions[S.file] = $("fVer").value;
  persist();
  fleetUpdate();
};
$("fTagAdd").addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  e.preventDefault();
  const t = $("fTagAdd").value.trim();
  if (!t) return;
  if (!F.options.includes(t)) F.options.push(t);
  if (!F.tags.includes(t)) F.tags.push(t);
  $("fTagAdd").value = "";
  renderFleetTags();
  fleetUpdate();
});
$("fCopy").onclick = async () => {
  if (!F.res) return;
  try {
    await navigator.clipboard.writeText(F.res.script);
    $("fCopy").textContent = "Kopiert";
    setTimeout(() => ($("fCopy").textContent = "Kopieren"), 1500);
  } catch (e) {
    /* Zwischenablage nicht verfügbar */
  }
};
$("fDownload").onclick = () => {
  if (!F.res) return;
  const a = el("a", {
    href: URL.createObjectURL(new Blob(["#!/usr/bin/env bash\nset -euo pipefail\n\n" + F.res.script], { type: "text/x-shellscript" })),
    download: "fleet-" + ($("fName").value.trim() || "config") + "-" + ($("fVer").value.trim() || "x") + ".sh",
  });
  document.body.append(a);
  a.click();
  a.remove();
};

function loadState(plugins) {
  S.order = [];
  S.plugins = {};
  S.collapsed = {};
  for (const p of plugins) {
    if (p.custom && !BYKEY[p.key])
      BYKEY[p.key] = { key: p.key, name: p.key, fields: [], src: "custom", cat: "Eigene", custom: true };
    S.plugins[p.key] = { key: p.key, values: p.values || {}, extra: p.extra || "" };
    S.order.push(p.key);
  }
  renderCatalog();
  renderEditor();
  refresh();
}
$("q").addEventListener("input", renderCatalog);
document.querySelectorAll(".chip").forEach(
  (c) =>
    (c.onclick = () => {
      filterMode = c.dataset.f;
      document.querySelectorAll(".chip").forEach((x) => x.setAttribute("aria-pressed", String(x === c)));
      renderCatalog();
    }),
);
$("cadd").onclick = () => {
  const k = $("ckey").value.trim();
  if (!/^[A-Za-z0-9_.\-]+$/.test(k)) {
    setStatus("bad", "Ungültiger Schlüssel. Erlaubt: Buchstaben, Ziffern, Punkt, Bindestrich, Unterstrich.");
    return;
  }
  if (!BYKEY[k]) BYKEY[k] = { key: k, name: k, fields: [], src: "custom", cat: "Eigene", custom: true };
  $("ckey").value = "";
  addPlugin(k);
};
$("ckey").addEventListener("keydown", (e) => {
  if (e.key === "Enter") $("cadd").click();
});
$("optComments").onchange = (e) => {
  S.comments = e.target.checked;
  refresh();
};

/* ---------------- Start ---------------- */
(async () => {
  const cj = await (await fetch("/api/catalog")).json();
  CAT = cj.plugins;
  CATS = cj.categories || [];
  CAT.forEach((c) => (BYKEY[c.key] = c));
  INFO = await (await fetch("/api/info")).json();
  $("ver").textContent = "v" + INFO.version + " · " + CAT.length + " Plugins";
  const saved = store.get();
  if (INFO.initial) {
    setFile(INFO.initial.path);
    savedText = null;
    openResult({ ok: true, ...INFO.initial }, INFO.initial.path.split(/[\\/]/).pop());
    savedText = lastText;
    persist();
    return;
  }
  if (saved && saved.order) {
    S.comments = !!saved.comments;
    $("optComments").checked = S.comments;
    for (const k of saved.order) {
      if (!BYKEY[k]) BYKEY[k] = { key: k, name: k, fields: [], src: "custom", cat: "Eigene", custom: true };
    }
    S.order = saved.order.filter((k) => saved.plugins[k]);
    S.plugins = saved.plugins;
    S.uploadName = saved.uploadName || "";
    S.osView = saved.osView || {};
    S.collapsed = saved.collapsed || {};
    S.mergeFiles = saved.mergeFiles || [];
    S.mergeDir = saved.mergeDir || "";
    S.fleet = saved.fleet || { server: "", versions: {} };
  }
  setFile((saved && saved.file) || "");
  renderCatalog();
  renderEditor();
  refresh();
  if (INFO.error) setStatus("bad", INFO.error);
})();
