const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
let S = null;
let savedTimer = 0;
let pairTimer = 0;

const ENERGY = { Zen: "Casi no se mueve. Ideal para concentrarte.", Normal: "Brinca y curiosea de vez en cuando.", Travieso: "Más inquieto y juguetón." };
const FMT = {
  pct: v => Math.round(v * 100) + "%",
  min: v => v + " min",
  st: v => (v > 0 ? "+" : "") + Number(v).toFixed(1),
  x: v => Number(v).toFixed(2) + "×",
  s: v => v + " s",
};
const CLIPS = {
  obs: "Usa tu OBS escondido. Graba juegos en pantalla completa exclusiva y es compatible con anti-cheat.",
  native: "Lo graba el sapo con FFmpeg. No graba pantalla completa exclusiva.",
  medal: "Manda tu atajo de Medal (F8). Algunos anti-cheat lo pueden ver mal.",
  gamebar: "Manda Win+Alt+G a la Xbox Game Bar. Algunos anti-cheat lo pueden ver mal.",
};

const svgUrl = svg => "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 3200);
}

function saved() {
  const el = $("#saved");
  el.textContent = "Guardado ✓";
  el.style.opacity = 1;
  clearTimeout(savedTimer);
  savedTimer = setTimeout(() => (el.style.opacity = 0), 1600);
}

async function put(path, value) {
  const [section, key] = path.split(".");
  const r = await pywebview.api.set(section, key, value);
  if (r.ok) {
    S.config[section][key] = r.value;
    saved();
  } else {
    toast("No se guardó: " + r.error);
    render();
  }
  return r.ok;
}

function get(path) {
  const [section, key] = path.split(".");
  return S.config[section][key];
}

function paintRange(input) {
  const p = ((input.value - input.min) / (input.max - input.min)) * 100;
  input.style.setProperty("--p", p + "%");
  const out = input.parentElement.querySelector("output");
  if (out) out.textContent = FMT[input.dataset.fmt](Number(input.value));
}

function fillSelect(sel, items, current) {
  sel.replaceChildren(...items.map(([v, label]) => new Option(label, v)));
  if (!items.some(([v]) => String(v) === String(current))) sel.append(new Option(current + " (no disponible aquí)", current));
  sel.value = String(current);
}

function render() {
  const c = S.config;
  $$(".seg[data-bind]").forEach(seg => {
    const v = String(get(seg.dataset.bind));
    $$("button", seg).forEach(b => b.setAttribute("aria-pressed", b.dataset.v === v));
  });
  $$("input[type=checkbox][data-bind]").forEach(i => (i.checked = !!get(i.dataset.bind)));
  $$("input[type=range][data-bind]").forEach(i => { i.value = get(i.dataset.bind); paintRange(i); });
  $$("input[type=text][data-bind]").forEach(i => (i.value = get(i.dataset.bind)));
  $("#energy-hint").textContent = ENERGY[c.pc.energy];
  $("#clips-hint").textContent = CLIPS[c.clips.method] || "";

  $$(".skin").forEach(el => el.setAttribute("aria-checked", el.dataset.id === c.pc.skin));
  fillSelect($("#monitor"), [["auto", "Automático"], ...S.monitors.map(m => [m.index, m.label])], c.pc.monitor);
  renderPin(c.pc.pin);

  const voices = S.voices[c.voice.engine === "local" ? "local" : "gemini"];
  fillSelect($("#voice"), voices.map(v => [v, v]), c.voice.voice);
  fillSelect($("#mic"), [["", "Predeterminado de Windows"], ...S.devices.inputs.map(d => [d, d.trim()])], c.voice.mic);
  fillSelect($("#speaker"), [["", "Predeterminado de Windows"], ...S.devices.outputs.map(d => [d, d.trim()])], c.voice.speaker);

  $("#key-card").classList.toggle("dim", c.brain.provider !== "gemini");
  renderKey();
  renderChips();
  renderStartup();
  renderPhone();
}

function renderPhone() {
  $("#pair-card").classList.toggle("dim", !S.config.phone.enabled);
  const list = $("#devices");
  if (!S.phone.devices.length) {
    const li = document.createElement("li");
    li.className = "empty";
    li.textContent = "Ningún celular vinculado.";
    list.replaceChildren(li);
    return;
  }
  list.replaceChildren(...S.phone.devices.map(d => {
    const li = document.createElement("li");
    const info = document.createElement("div");
    const name = document.createElement("strong");
    name.textContent = d.device;
    const when = document.createElement("span");
    when.className = "hint";
    when.textContent = d.date ? "Vinculado el " + d.date.replace("T", " ").slice(0, 16) : "Vinculado";
    info.append(name, when);
    const b = document.createElement("button");
    b.className = "btn danger";
    b.textContent = "Revocar";
    b.setAttribute("aria-label", "Revocar " + d.device);
    b.onclick = async () => {
      const r = await pywebview.api.phone_revoke(d.id);
      if (r.phone) S.phone = r.phone;
      if (r.ok) saved(); else toast(r.error);
      renderPhone();
    };
    li.append(info, b);
    return li;
  }));
}

function hideCode(msg, kind) {
  clearInterval(pairTimer);
  $("#pair-box").hidden = true;
  const res = $("#pair-result");
  res.className = "result " + (kind || "");
  res.textContent = msg || "";
}

function showCode(r) {
  const before = S.phone.devices.length;
  let left = r.expires_in;
  let n = 0;
  $("#pair-box").hidden = false;
  $("#pair-code").textContent = r.code.slice(0, 3) + " " + r.code.slice(3);
  $("#pair-ip").textContent = r.ips.length ? r.ips.map(ip => ip + ":" + r.port).join(", ") : "no encontré tu IP local";
  const paint = () => { const s = Math.max(0, left); $("#pair-left").textContent = Math.floor(s / 60) + ":" + String(s % 60).padStart(2, "0"); };
  paint();
  clearInterval(pairTimer);
  pairTimer = setInterval(async () => {
    left -= 1;
    paint();
    if (++n % 2 && left > 0) return;
    const st = await pywebview.api.phone_state();
    S.phone = st;
    if (st.devices.length > before && !st.pending) { hideCode("¡Celular vinculado!", "ok"); renderPhone(); }
    else if (!st.pending) hideCode(left <= 0 ? "El código venció. Genera otro." : "El código ya no sirve. Genera otro.", "bad");
  }, 1000);
}

function renderPin(pin) {
  $("#pin-text").textContent = pin ? `Está sentado en su nenúfar (${Math.round(pin.x)}, ${Math.round(pin.y)}).` : "Anda libre por el escritorio.";
  $("#unpin").disabled = !pin;
}

function renderKey() {
  const pill = $("#key-pill");
  pill.classList.toggle("ok", S.has_key || S.env_key);
  pill.textContent = S.has_key ? "Key guardada" : S.env_key ? "Usando GEMINI_API_KEY" : "Sin key";
  $("#key-del").disabled = !S.has_key;
  $("#key-test").disabled = !S.has_key && !S.env_key;
}

function renderChips() {
  const box = $("#chips");
  box.replaceChildren(...S.config.brain.blacklist.map(w => {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.append(w);
    const x = document.createElement("button");
    x.textContent = "×";
    x.title = "Quitar " + w;
    x.setAttribute("aria-label", "Quitar " + w);
    x.onclick = () => put("brain.blacklist", S.config.brain.blacklist.filter(v => v !== w)).then(renderChips);
    chip.append(x);
    return chip;
  }));
}

function renderStartup() {
  const st = S.startup;
  const auto = $("#auto");
  auto.checked = st.enabled;
  auto.disabled = !st.available && !st.enabled;
  if (document.activeElement !== $("#auto-cmd")) $("#auto-cmd").value = st.command;
  $("#auto-hint").textContent = st.available
    ? (st.enabled ? "El sapo arrancará al iniciar sesión." : "Apagado.")
    : (st.found ? "La ruta del comando no existe." : "No encontré Sapo.exe. Escribe el comando abajo para habilitarlo.");
}

function bind() {
  $$("nav button").forEach(b => (b.onclick = () => {
    $$("nav button").forEach(x => x.setAttribute("aria-selected", x === b));
    $$(".tab").forEach(t => (t.hidden = t.id !== "tab-" + b.dataset.tab));
    $("main").scrollTop = 0;
  }));

  $$(".seg[data-bind]").forEach(seg => $$("button", seg).forEach(b => (b.onclick = async () => {
    const path = seg.dataset.bind;
    const v = seg.dataset.type === "int" ? Number(b.dataset.v) : b.dataset.v;
    if (await put(path, v)) {
      if (path === "voice.engine") {
        const list = S.voices[v === "local" ? "local" : "gemini"];
        if (!list.includes(S.config.voice.voice)) await put("voice.voice", list[0]);
      }
      render();
    }
  })));

  $$("input[type=checkbox][data-bind]").forEach(i => (i.onchange = () => put(i.dataset.bind, i.checked)));
  $$("input[type=range][data-bind]").forEach(i => {
    i.oninput = () => paintRange(i);
    i.onchange = () => put(i.dataset.bind, i.dataset.type === "int" ? parseInt(i.value, 10) : Number(i.value));
  });
  $$("input[type=text][data-bind]").forEach(i => (i.onchange = async () => { if (await put(i.dataset.bind, i.value)) i.value = get(i.dataset.bind); }));
  $$("select[data-bind]").forEach(s => (s.onchange = () => {
    const v = s.dataset.type === "monitor" && s.value !== "auto" ? Number(s.value) : s.value;
    put(s.dataset.bind, v);
  }));

  $("#unpin").onclick = async () => {
    const r = await pywebview.api.unpin();
    if (r.ok) { S.config.pc.pin = null; renderPin(null); saved(); } else toast(r.error);
  };

  $("#key-save").onclick = saveKey;
  $("#key").onkeydown = e => { if (e.key === "Enter") saveKey(); };
  $("#key-test").onclick = async () => {
    const res = $("#key-result");
    res.className = "result";
    res.textContent = "Probando…";
    $("#key-test").disabled = true;
    const r = await pywebview.api.test_key();
    res.className = "result " + (r.ok ? "ok" : "bad");
    res.textContent = r.message;
    renderKey();
  };
  $("#key-del").onclick = async () => {
    const r = await pywebview.api.delete_key();
    if (r.ok) { S.has_key = false; renderKey(); $("#key-result").className = "result"; $("#key-result").textContent = "Key borrada de esta PC."; }
    else toast(r.error);
  };

  const addChip = async () => {
    const inp = $("#chip-in");
    const w = inp.value.trim().toLowerCase();
    if (!w) return;
    if (S.config.brain.blacklist.includes(w)) { inp.value = ""; return; }
    if (await put("brain.blacklist", [...S.config.brain.blacklist, w])) { inp.value = ""; renderChips(); }
  };
  $("#chip-add").onclick = addChip;
  $("#chip-in").onkeydown = e => { if (e.key === "Enter") addChip(); };

  $("#dev-refresh").onclick = async () => { S.devices = await pywebview.api.devices(); render(); saved(); };

  $("#phone-on").onchange = async () => { await put("phone.enabled", $("#phone-on").checked); renderPhone(); };
  $("#pair-new").onclick = async () => {
    const r = await pywebview.api.phone_pair();
    if (!r.ok) { toast(r.error); return; }
    hideCode(S.config.phone.enabled ? "" : "Activa el enlace para que el celular pueda conectarse.");
    showCode(r);
  };
  $("#pair-cancel").onclick = async () => {
    const r = await pywebview.api.phone_cancel();
    if (r.ok) hideCode("Código cancelado."); else toast(r.error);
  };

  $("#auto").onchange = () => applyStartup($("#auto").checked);
  $("#auto-cmd").onchange = () => applyStartup($("#auto").checked);

  $$("[data-url]").forEach(a => (a.onclick = e => { e.preventDefault(); pywebview.api.open_url(a.dataset.url); }));
  $("#open-home").onclick = () => pywebview.api.open_folder();
}

async function saveKey() {
  const inp = $("#key");
  const key = inp.value.trim();
  if (!key) return;
  const r = await pywebview.api.save_key(key);
  inp.value = "";
  const res = $("#key-result");
  if (r.ok) {
    S.has_key = true;
    res.className = "result ok";
    res.textContent = "Key guardada y cifrada. Dale a Probar para revisarla.";
    saved();
  } else {
    res.className = "result bad";
    res.textContent = r.error;
  }
  renderKey();
}

async function applyStartup(enabled) {
  const r = await pywebview.api.set_autostart(enabled, $("#auto-cmd").value);
  S.startup = r.startup;
  if (r.ok) saved(); else toast(r.error);
  renderStartup();
}

function gallery() {
  $("#skins").replaceChildren(...S.skins.map(s => {
    const b = document.createElement("button");
    b.className = "skin";
    b.dataset.id = s.id;
    b.setAttribute("role", "radio");
    b.style.setProperty("--tint", `color-mix(in srgb, ${s.body} 32%, white)`);
    const img = document.createElement("img");
    img.alt = "";
    if (s.svg) img.src = svgUrl(s.svg);
    const name = document.createElement("span");
    name.textContent = s.name;
    b.append(img, name);
    b.onclick = async () => { if (await put("pc.skin", s.id)) render(); };
    return b;
  }));
  $("#skins").setAttribute("role", "radiogroup");
  const own = S.skins.find(s => s.id === "clasico") || S.skins[0];
  if (own && own.svg) { $("#brand-img").src = svgUrl(own.svg); $("#about-img").src = svgUrl(own.svg); }
}

async function start() {
  S = await pywebview.api.state();
  $("#version").textContent = "v" + S.about.version;
  $("#home").textContent = S.about.home;
  gallery();
  bind();
  render();
  const first = START_TAB && $(`nav button[data-tab="${START_TAB}"]`);
  if (first) first.click();
  setInterval(async () => {
    const pin = await pywebview.api.pin();
    if (JSON.stringify(pin) !== JSON.stringify(S.config.pc.pin)) { S.config.pc.pin = pin; renderPin(pin); }
  }, 2000);
}

if (window.pywebview && window.pywebview.api && window.pywebview.api.state) start();
else window.addEventListener("pywebviewready", start, { once: true });
