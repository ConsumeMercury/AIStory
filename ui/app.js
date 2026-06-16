/** AIStory — story-first web client */

const $ = (sel) => document.querySelector(sel);

let state = null;
let busy = false;
let openModalKind = null;

const storyLog = $("#story-log");
const sidebar = $("#sidebar");
const statusBar = $("#status-bar");
const chipRow = $("#chip-row");
const actionForm = $("#action-form");
const actionInput = $("#action-input");
const sendBtn = $("#send-btn");
const modal = $("#modal");
const modalBackdrop = $("#modal-backdrop");
const modalTitle = $("#modal-title");
const modalBody = $("#modal-body");

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(apiErrorDetail(data, res.statusText));
  return data;
}

function apiErrorDetail(data, fallback) {
  const d = data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x.msg || JSON.stringify(x)).join("; ");
  if (d && typeof d === "object") return d.msg || JSON.stringify(d);
  return fallback || data?.message || "Request failed";
}

function attrEsc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;");
}

function esc(s) {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function rarityClass(r) {
  return "r-" + (r || "common");
}

function isMetaText(text) {
  if (!text) return false;
  const t = text.trim();
  return t.startsWith("  ") || t.startsWith("=") || t.startsWith("Commands");
}

function labelize(cmd) {
  if (!cmd) return "";
  let s = cmd.replace(/^ask\s+/i, "Ask ");
  s = s.replace(/^talk to\s+/i, "Talk to ");
  s = s.replace(/^go to\s+/i, "Travel to ");
  if (s.length > 28) s = s.slice(0, 26) + "…";
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function titleCase(s) {
  if (!s) return "";
  return String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function scrollStoryToEnd() {
  requestAnimationFrame(() => {
    storyLog.scrollTop = storyLog.scrollHeight;
  });
}

function statBar(label, current, max, cls) {
  const pct = max ? Math.max(0, Math.min(100, Math.round((100 * current) / max))) : 0;
  return `
    <div class="stat-bar-row">
      <span>${label}</span>
      <div class="track"><div class="fill ${cls || ""}" style="width:${pct}%"></div></div>
      <span class="stat-val">${current}/${max}</span>
    </div>`;
}

function relBar(label, bar) {
  if (!bar || bar.pct == null) return "";
  return `
    <div class="rel-bar">
      <span>${label}</span>
      <div class="track"><div class="fill" style="width:${bar.pct}%"></div></div>
    </div>`;
}

function formatDelta(n) {
  if (n === 0 || n == null) return "±0";
  return n > 0 ? `+${n}` : String(n);
}

function deltaClass(n) {
  if (n > 0) return "delta-pos";
  if (n < 0) return "delta-neg";
  return "delta-neutral";
}

function renderDeltaRow(label, delta, after, suffix = "") {
  return `
    <div class="delta-row">
      <span class="delta-label">${esc(label)}${suffix}</span>
      <span class="delta-value ${deltaClass(delta)}">
        ${formatDelta(delta)}
        ${after != null ? `<span class="delta-after"> → ${after}</span>` : ""}
      </span>
    </div>`;
}

function renderDeltaPanel(turn) {
  const body = $("#delta-body");
  const panel = $("#delta-panel");
  if (!body) return;

  const d = turn?.deltas;
  if (!d || d.empty) {
    body.innerHTML = `<p class="delta-empty">${
      turn ? "No changes this turn." : "Take an action to see stat changes."
    }</p>`;
    return;
  }

  let html = "";

  if (d.skill_check) {
    const sc = d.skill_check;
    const skill = titleCase(sc.skill || sc.kind || "Check");
    const outcome = sc.success ? "Success" : "Failure";
    const detail = [
      sc.roll != null ? `d${sc.roll}` : null,
      sc.total != null ? `→ ${sc.total}` : null,
      sc.difficulty != null ? `vs ${sc.difficulty}` : null,
    ]
      .filter(Boolean)
      .join(" ");
    html += `
      <div class="delta-skill ${sc.success ? "delta-pos" : "delta-neg"}">
        <span class="delta-skill-label">${esc(skill)}</span>
        <span>${esc(outcome)}${detail ? ` · ${esc(detail)}` : ""}</span>
        ${sc.consequence ? `<div class="delta-after">${esc(sc.consequence)}</div>` : ""}
      </div>`;
  }

  if (d.player?.length) {
    html += `<div class="delta-section"><div class="delta-section-label">You</div>`;
    for (const row of d.player) {
      html += renderDeltaRow(row.label, row.delta, row.after);
    }
    html += `</div>`;
  }

  if (d.npcs?.length) {
    html += `<div class="delta-section"><div class="delta-section-label">Others</div>`;
    for (const row of d.npcs) {
      const statLabel = row.stat === "met" ? "met" : titleCase(row.stat);
      const suffix = row.stat === "met" ? "" : ` · ${statLabel}`;
      html += renderDeltaRow(row.name, row.delta, row.after, suffix);
    }
    html += `</div>`;
  }

  if (d.items?.length) {
    html += `<div class="delta-section"><div class="delta-section-label">Found</div>`;
    for (const item of d.items) {
      html += `<div class="delta-item"><span class="rarity ${rarityClass(item.rarity)}">${esc(item.rarity || "common")}</span>${esc(item.name)}</div>`;
    }
    html += `</div>`;
  }

  if (d.rumors?.length) {
    html += `<div class="delta-section"><div class="delta-section-label">Rumors</div>`;
    for (const rumor of d.rumors) {
      html += `<div class="delta-rumor">${esc(rumor)}</div>`;
    }
    html += `</div>`;
  }

  if (d.other?.length) {
    html += `<div class="delta-section"><div class="delta-section-label">World</div>`;
    for (const row of d.other) {
      html += `<div class="delta-row"><span class="delta-label">${esc(row.label)}</span><span class="delta-value delta-neutral">${esc(row.text)}</span></div>`;
    }
    html += `</div>`;
  }

  body.innerHTML = html || `<p class="delta-empty">No changes this turn.</p>`;

  if (panel) {
    panel.classList.remove("delta-flash");
    void panel.offsetWidth;
    panel.classList.add("delta-flash");
  }
}

function updateSessionControls() {
  const btn = $("#btn-undo");
  if (btn) btn.disabled = busy || !state?.session?.can_undo;
}

function setBadge(el, count) {
  if (!el) return;
  if (count > 0) {
    el.textContent = count;
    el.classList.remove("hidden");
  } else {
    el.textContent = "";
    el.classList.add("hidden");
  }
}

function setOptionalText(el, text, hiddenClass = "hidden") {
  if (!el) return;
  if (text) {
    el.textContent = text;
    el.classList.remove(hiddenClass);
  } else {
    el.textContent = "";
    el.classList.add(hiddenClass);
  }
}

function ensureSidebarVisible() {
  document.body.classList.remove("layout-drawer");
  sidebar?.classList.remove("drawer-open", "hidden");
  $("#sidebar-backdrop")?.classList.remove("visible");
  if (sidebar) {
    sidebar.style.removeProperty("display");
    sidebar.style.removeProperty("visibility");
    sidebar.style.removeProperty("opacity");
  }
}

function syncLayoutMode() {
  document.body.classList.toggle("layout-mobile", window.matchMedia("(max-width: 900px)").matches);
  ensureSidebarVisible();
}

/* ── Status bar ── */
function renderStatusBar() {
  if (!state?.header) return;
  const h = state.header;
  const who = state.player?.name;

  const nameEl = $("#hdr-name");
  const nameSep = $("#hdr-name-sep");
  if (nameEl) {
    if (who) {
      nameEl.textContent = who;
      nameEl.classList.remove("hidden");
      nameSep?.classList.remove("hidden");
    } else {
      nameEl.classList.add("hidden");
      nameSep?.classList.add("hidden");
    }
  }

  const timeEl = $("#hdr-time");
  const weatherEl = $("#hdr-weather");
  const placeEl = $("#hdr-place");
  const healthBar = $("#hdr-health-bar");
  const healthVal = $("#hdr-health-val");
  const staminaBar = $("#hdr-stamina-bar");
  const staminaVal = $("#hdr-stamina-val");
  const wealthEl = $("#hdr-wealth");

  if (timeEl) timeEl.textContent = h.time || "—";
  if (weatherEl) weatherEl.textContent = h.weather || "—";
  if (placeEl) placeEl.textContent = h.place_short || "—";
  if (healthBar) healthBar.style.width = `${h.health?.pct ?? 0}%`;
  if (healthVal) healthVal.textContent = `${h.health?.current ?? 0}/${h.health?.max ?? 0}`;
  if (staminaBar) staminaBar.style.width = `${h.stamina?.pct ?? 0}%`;
  if (staminaVal) staminaVal.textContent = `${h.stamina?.current ?? 0}/${h.stamina?.max ?? 0}`;
  if (wealthEl) wealthEl.textContent = `${h.wealth ?? 0}c`;
}

/* ── Sidebar ── */
function renderSidebar() {
  if (!state) return;
  const p = state.player || {};
  const bondCount = (state.relations_full || []).length;
  const rumorCount = (state.rumors_full || []).length;
  const invCount = (state.inventory_panel?.inventory || []).length;
  const w = state.world_sidebar || {};

  const nameEl = $("#sb-name");
  const metaEl = $("#sb-meta");
  const motivationEl = $("#sb-motivation");
  const goalsEl = $("#sb-goals");
  const hintEl = $("#sb-hint");
  const weatherEl = $("#sb-weather");
  const moodEl = $("#sb-mood");

  if (nameEl) nameEl.textContent = p.name || "You";
  if (metaEl) {
    metaEl.textContent = `${titleCase(p.background || "wanderer")} · Level ${p.level ?? 1}`;
  }
  setOptionalText(motivationEl, p.motivation || "");

  if (goalsEl) {
    const goals = (p.goals || []).slice(0, 2);
    if (goals.length) {
      goalsEl.innerHTML = goals.map((g) => `<li>${esc(g.text)}</li>`).join("");
      goalsEl.classList.remove("hidden");
    } else {
      goalsEl.innerHTML = "";
      goalsEl.classList.add("hidden");
    }
  }

  setOptionalText(hintEl, p.goal_hint || "");
  if (weatherEl) weatherEl.textContent = w.weather || "—";
  if (moodEl) moodEl.textContent = w.district_mood || "—";

  setBadge($("#badge-inv"), invCount);
  setBadge($("#badge-bonds"), bondCount);
  setBadge($("#badge-rumors"), rumorCount);
  updateSessionControls();
}

function initSidebar() {
  sidebar?.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-modal]");
    if (btn) openModal(btn.dataset.modal);
  });
  window.addEventListener("resize", syncLayoutMode);
  syncLayoutMode();
}

function renderChips(hints) {
  chipRow.innerHTML = "";
  (hints || []).slice(0, 5).forEach((cmd) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.textContent = labelize(cmd);
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      submitAction(cmd);
    });
    chipRow.appendChild(btn);
  });
}

/* ── Story manuscript blocks ── */
function appendTurn(turn, scene, isMeta) {
  if (!scene || !String(scene).trim()) return;

  const block = document.createElement("article");
  block.className = "turn-block";

  const meta = turn || {};
  const timeLoc = [meta.time, meta.location].filter(Boolean).join(" • ");
  const showRule = storyLog.children.length > 0;

  block.innerHTML = `
    ${showRule ? `<hr class="turn-rule" />` : ""}
    ${timeLoc ? `<div class="turn-meta">${esc(timeLoc)}</div>` : ""}
    ${meta.action ? `<div class="turn-action">${esc(meta.action)}</div>` : ""}
    <div class="turn-prose ${isMeta ? "meta" : ""}">${esc(String(scene).trim())}</div>
  `;

  storyLog.appendChild(block);

  if (turn?.new_place?.description) {
    appendPlaceNote(turn.new_place);
  }

  scrollStoryToEnd();
}

function appendPlaceNote(place) {
  const block = document.createElement("aside");
  block.className = "place-note";
  block.innerHTML = `
    <div class="place-note-head">${esc(place.name)}${place.subtitle ? ` · ${esc(place.subtitle)}` : ""}</div>
    <div class="place-note-body">${esc(place.description)}</div>
  `;
  storyLog.appendChild(block);
}

function appendPending(action) {
  const block = document.createElement("article");
  block.className = "turn-block pending-turn";
  block.id = "pending-turn";
  const showRule = storyLog.children.length > 0;
  block.innerHTML = `
    ${showRule ? `<hr class="turn-rule" />` : ""}
    <div class="turn-action">${esc(action)}</div>
    <div class="turn-prose system">Writing…</div>
  `;
  storyLog.appendChild(block);
  scrollStoryToEnd();
}

function clearPending() {
  document.getElementById("pending-turn")?.remove();
}

function hydrateStoryHistory(blocks) {
  if (!blocks?.length) return;
  for (const block of blocks) {
    appendTurn(
      { action: block.action, time: block.time, location: block.location },
      block.scene,
      block.meta
    );
  }
  scrollStoryToEnd();
}

function appendSystem(text) {
  const block = document.createElement("article");
  block.className = "turn-block";
  block.innerHTML = `<div class="turn-prose system">${esc(text)}</div>`;
  storyLog.appendChild(block);
  scrollStoryToEnd();
}

/* ── Modals ── */
function closeModal() {
  openModalKind = null;
  modal.classList.add("hidden");
  modalBackdrop.classList.add("hidden");
  document.body.classList.remove("modal-open");
}

function openModal(kind) {
  if (!state) return;
  openModalKind = kind;
  modal.classList.remove("hidden");
  modalBackdrop.classList.remove("hidden");
  document.body.classList.add("modal-open");

  const titles = {
    inventory: "Inventory",
    relations: "Bonds",
    rumors: "Known Rumors",
    codex: "Codex",
    journal: "Timeline",
    map: "Travel",
    character: "Character Sheet",
    world: "World",
    saves: "Save / load",
  };
  modalTitle.textContent = titles[kind] || "Panel";

  if (kind === "inventory") {
    modalBody.innerHTML = renderInventoryModal();
    bindInventoryActions();
  } else if (kind === "relations") {
    modalBody.innerHTML = renderRelationsModal();
  } else if (kind === "rumors") {
    modalBody.innerHTML = renderRumorsModal();
  } else if (kind === "codex") {
    modalBody.innerHTML = renderCodexModal();
  } else if (kind === "journal") {
    modalBody.innerHTML = renderTimelineModal();
  } else if (kind === "map") {
    modalBody.innerHTML = renderMapModal();
    bindMapActions();
  } else if (kind === "character") {
    modalBody.innerHTML = renderCharacterModal();
  } else if (kind === "world") {
    modalBody.innerHTML = renderWorldModal();
  } else if (kind === "saves") {
    renderSavesModal();
  }
}

async function renderSavesModal() {
  modalBody.innerHTML = "<p class=\"sheet-note\">Loading saves…</p>";
  try {
    const data = await api("/api/saves");
    const slots = data.slots || [];
    let html = `
      <div class="sheet-section">
        <h4>Save current game</h4>
        <div class="save-row">
          <input type="text" id="save-slot-id" placeholder="slot name" maxlength="32" />
          <button type="button" class="qa-btn" id="save-slot-btn">Save</button>
        </div>
      </div>
      <div class="sheet-section">
        <h4>Saved games</h4>`;
    if (!slots.length) {
      html += `<p class="sheet-note">No save slots yet.</p>`;
    } else {
      html += slots.map((s) => `
        <div class="save-slot-row">
          <div><strong>${esc(s.label || s.id)}</strong>
            ${s.character ? `<span class="sheet-note"> · ${esc(s.character)}</span>` : ""}
          </div>
          <button type="button" class="qa-btn" data-load-slot="${attrEsc(s.id)}">Load</button>
        </div>`).join("");
    }
    html += `</div>`;
    modalBody.innerHTML = html;
    $("#save-slot-btn")?.addEventListener("click", async () => {
      const id = ($("#save-slot-id")?.value || "").trim() || `save_${Date.now()}`;
      try {
        await api(`/api/saves/${encodeURIComponent(id)}`, { method: "POST", body: JSON.stringify({ label: id }) });
        appendSystem(`Game saved to slot “${id}”.`);
        renderSavesModal();
      } catch (err) {
        appendSystem(err.message || "Save failed.");
      }
    });
    modalBody.querySelectorAll("[data-load-slot]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const slot = btn.getAttribute("data-load-slot");
        try {
          const res = await api(`/api/saves/${encodeURIComponent(slot)}/load`, { method: "POST" });
          if (res.state) await startGame(res);
          appendSystem(`Loaded save “${slot}”.`);
          closeModal();
        } catch (err) {
          appendSystem(err.message || "Load failed.");
        }
      });
    });
  } catch (err) {
    modalBody.innerHTML = `<p class="sheet-note">${esc(err.message || "Could not list saves.")}</p>`;
  }
}

async function undoLastTurn() {
  if (busy) return;
  setBusy(true);
  try {
    const res = await api("/api/undo", { method: "POST" });
    if (res.state) {
      state = res.state;
      storyLog.innerHTML = "";
      hydrateStoryHistory(state.story_history || []);
      renderStatusBar();
      renderSidebar();
      renderDeltaPanel(null);
      refreshOpenModal();
      appendSystem("Undid the last turn.");
    }
  } catch (err) {
    appendSystem(err.message || "Nothing to undo.");
  } finally {
    setBusy(false);
  }
}

function renderCharacterModal() {
  const p = state.player || {};
  const attrs = Object.entries(p.attributes || {});
  const skills = Object.entries(p.skills || {});
  const injuries = p.injuries || [];
  const lc = p.last_check;

  let html = `
    <div class="sheet-header">
      <h3>${esc(p.name || "You")}</h3>
      <p>${esc(titleCase(p.background || "wanderer"))} · Level ${p.level}</p>
      ${p.appearance ? `<p class="sheet-note">${esc(p.appearance)}</p>` : ""}
      ${p.motivation ? `<p class="sheet-note">${esc(p.motivation)}</p>` : ""}
    </div>
    <div class="sheet-section">
      <h4>Vitals</h4>
      ${statBar("Health", p.health?.current, p.health?.max, "health")}
      ${statBar("Stamina", p.stamina?.current, p.stamina?.max, "stamina")}
      ${statBar("Stress", p.stress?.current, p.stress?.max, "stress")}
    </div>
    <div class="sheet-section">
      <h4>Combat</h4>
      <div class="stat-grid">
        <span>Attack</span><span>${p.combat?.attack ?? "—"}</span>
        <span>Defense</span><span>${p.combat?.defense ?? "—"}</span>
        <span>Speed</span><span>${p.combat?.speed ?? "—"}</span>
      </div>
    </div>`;

  if (attrs.length) {
    html += `
      <div class="sheet-section">
        <h4>Attributes</h4>
        <div class="stat-grid">${attrs.map(([k, v]) => `<span>${esc(titleCase(k))}</span><span>${v}</span>`).join("")}</div>
      </div>`;
  }

  if (skills.length) {
    html += `
      <div class="sheet-section">
        <h4>Skills</h4>
        <div class="stat-grid">${skills.map(([k, v]) => `<span>${esc(titleCase(k))}</span><span>Lv ${v.level}${v.xp ? ` · ${v.xp} xp` : ""}</span>`).join("")}</div>
      </div>`;
  }

  if (injuries.length) {
    html += `
      <div class="sheet-section">
        <h4>Injuries</h4>
        <ul class="facts">${injuries.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>
      </div>`;
  }

  if (p.goals?.length) {
    html += `
      <div class="sheet-section">
        <h4>Goals</h4>
        <ul class="facts">${p.goals.map((g) => `<li>${esc(g.text)}${g.target ? ` (${g.progress}/${g.target})` : ""}</li>`).join("")}</ul>
      </div>`;
  }

  if (lc) {
    html += `
      <div class="sheet-section">
        <h4>Last check</h4>
        <p class="sheet-note">${esc(lc.skill || lc.kind || "Check")}: roll ${lc.roll ?? "?"} + mods = ${lc.total ?? "?"} vs ${lc.difficulty ?? "?"} — ${lc.success ? "success" : "failure"}${lc.consequence ? ` (${esc(lc.consequence)})` : ""}</p>
      </div>`;
  }

  html += `<p class="sheet-wealth">Coin on hand: ${p.wealth ?? 0}c</p>`;
  return html;
}

function renderWorldModal() {
  const w = state.world_sidebar || {};
  const world = state.world || {};
  const facHtml = (w.factions || [])
    .map((f) => `<div class="world-line"><strong>${esc(f.name)}</strong> ${esc(f.standing)}</div>`)
    .join("");

  let html = `
    <div class="sheet-section">
      <h4>Location</h4>
      <div class="world-line"><strong>City</strong> ${esc(world.city || "?")}</div>
      <div class="world-line"><strong>District</strong> ${esc(world.district || "?")}</div>
    </div>
    <div class="sheet-section">
      <h4>Conditions</h4>
      <div class="world-line"><strong>Weather</strong> ${esc(w.weather)}</div>
      <div class="world-line"><strong>Season</strong> ${esc(w.season || world.season || "—")}</div>
      <div class="world-line"><strong>District mood</strong> ${esc(w.district_mood)}</div>`;
  if (w.prosperity != null) {
    html += `<div class="world-line"><strong>Prosperity</strong> ${w.prosperity}</div>`;
  }
  if (w.crime != null) {
    html += `<div class="world-line"><strong>Crime</strong> ${w.crime}</div>`;
  }
  html += `</div>`;

  if (world.storyline?.title) {
    html += `
      <div class="sheet-section">
        <h4>Local storyline</h4>
        <p class="sheet-note"><strong>${esc(world.storyline.title)}</strong></p>
        <p class="sheet-note">${esc(world.storyline.current || "")}</p>
      </div>`;
  }

  html += `
    <div class="sheet-section">
      <h4>Faction standing</h4>
      ${facHtml || `<p class="empty-note">No notable faction reputation yet.</p>`}
    </div>`;

  return html;
}

function renderInventoryModal() {
  const inv = state.inventory_panel || {};
  const slots = inv.equipment || {};
  let html = `<p class="equip-slot-row">Coin: <span>${inv.wealth}c</span></p>`;
  for (const slot of ["weapon", "armor", "trinket"]) {
    const item = slots[slot];
    html += `<p class="equip-slot-row">${slot}: <span>${item ? esc(item.name) : "—"}</span>`;
    if (item) html += ` <button type="button" data-unequip="${slot}">Remove</button>`;
    html += `</p>`;
  }
  const bonuses = inv.bonuses || {};
  const bonusParts = [
    ...Object.entries(bonuses.stats || {}).map(([k, v]) => `+${v} ${k}`),
    ...Object.entries(bonuses.skills || {}).map(([k, v]) => `+${v} ${k}`),
  ];
  if (bonusParts.length) {
    html += `<p class="sheet-note">Equipped bonuses: ${esc(bonusParts.join(", "))}</p>`;
  }
  html += `<hr class="turn-rule" style="margin:0.75rem 0" />`;
  const items = inv.inventory || [];
  if (!items.length) {
    html += `<p class="empty-note">Pack is empty.</p>`;
  } else {
    html += items
      .map((item) => {
        const btns = [];
        if (item.equippable) btns.push(`<button type="button" data-equip="${item.index}">Equip</button>`);
        if (item.consumable) btns.push(`<button type="button" data-use="${item.index}">Use</button>`);
        return `
          <div class="item-row ${rarityClass(item.rarity)}">
            <div class="item-info">
              <div class="iname">${esc(item.name)}</div>
              <div class="imeta">${esc(item.rarity)} · ${item.value ?? "?"}c${item.mod_summary ? " · " + esc(item.mod_summary) : ""}</div>
            </div>
            <div class="item-btns">${btns.join("")}</div>
          </div>`;
      })
      .join("");
  }
  return html;
}

function bindInventoryActions() {
  modalBody.querySelectorAll("[data-equip]").forEach((b) =>
    b.addEventListener("click", () => {
      closeModal();
      submitAction(`equip ${b.dataset.equip}`);
    })
  );
  modalBody.querySelectorAll("[data-use]").forEach((b) =>
    b.addEventListener("click", () => {
      closeModal();
      submitAction(`use ${b.dataset.use}`);
    })
  );
  modalBody.querySelectorAll("[data-unequip]").forEach((b) =>
    b.addEventListener("click", () => {
      closeModal();
      submitAction(`unequip ${b.dataset.unequip}`);
    })
  );
}

function renderRelationsModal() {
  const cards = state.relations_full || [];
  if (!cards.length) {
    return `<p class="empty-note">No one you know by name yet. Learn someone's name before they appear here.</p>`;
  }
  return cards
    .map(
      (r, i) => `
    <details class="bond-profile"${i === 0 ? " open" : ""}>
      <summary>
        <span class="bond-name">${esc(r.name)}</span>
        <span class="bond-state">${esc(r.state)}${r.is_focus ? " · focus" : ""}</span>
      </summary>
      <div class="bond-body">
        ${r.description ? `<p class="bond-desc">${esc(r.description)} · ${esc(r.gender || "")}</p>` : ""}
        ${relBar("Trust", r.bars.trust)}
        ${relBar("Respect", r.bars.respect)}
        ${relBar("Fear", r.bars.fear)}
        ${relBar("Affection", r.bars.affection)}
        ${relBar("Familiarity", r.bars.familiarity)}
        ${r.facts?.length ? `<ul class="facts">${r.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
      </div>
    </details>`
    )
    .join("");
}

function renderRumorsModal() {
  const rumors = state.rumors_full || [];
  if (!rumors.length) return `<p class="empty-note">Nothing whispered yet — explore and talk.</p>`;
  return `<ul>${rumors.map((r) => `<li class="rumor-item">${r.local ? "<span class=\"rumor-local\">local</span> " : ""}${esc(r.text)}</li>`).join("")}</ul>`;
}

function renderCodexModal() {
  const c = state.codex || {};
  const section = (title, items, fmt) => {
    if (!items?.length) return "";
    return `<div class="codex-cat"><h4>${title}</h4><ul>${items.map(fmt).join("")}</ul></div>`;
  };
  return (
    section("People", c.people, (p) => `<li>${esc(p.name)}${p.role ? ` — ${esc(p.role)}` : ""}</li>`) +
    section("Places", c.places, (p) => {
      const sub = p.subtitle ? `<span class="place-sub">${esc(p.subtitle)}</span>` : "";
      const desc = p.description ? `<p class="place-desc">${esc(p.description)}</p>` : "";
      const meta = p.visits > 1 ? `<span class="place-visits">Visited ${p.visits}×</span>` : "";
      return `<li class="place-entry"><strong>${esc(p.name)}</strong> ${sub}${meta}${desc}</li>`;
    }) +
    section("Institutions", c.institutions, (i) => `<li>${esc(i.name)} (${esc(i.type)})</li>`) +
    section("Factions", c.factions, (f) => `<li>${esc(f.name)} — ${esc(f.standing)}</li>`) +
    section("History", c.history, (h) => `<li><em>${esc(h.when)}</em> ${esc(h.official || h.folk)}</li>`) ||
    `<p class="empty-note">Your codex fills as you explore.</p>`
  );
}

function renderTimelineModal() {
  const tl = state.timeline || [];
  if (!tl.length) return `<p class="empty-note">Your story has not begun.</p>`;
  return tl
    .map(
      (day) => `
    <div class="timeline-day">
      <h4>Day ${day.day}</h4>
      <ul>${day.events.map((e) => `<li>${esc(e.action || e.kind)}${e.excerpt && e.excerpt !== "[scene ok]" ? ` — ${esc(e.excerpt)}` : ""}</li>`).join("")}</ul>
    </div>`
    )
    .join("");
}

function renderMapModal() {
  const dests = state.world?.destinations || [];
  if (!dests.length) return `<p class="empty-note">Nowhere obvious to travel from here.</p>`;
  return dests
    .map(
      (d) => `
    <div class="map-row">
      <button type="button" data-travel="${attrEsc(d.id)}">
        <span class="map-name">${esc(d.name)}</span>
        <span class="map-detail">${esc(d.detail || d.region || "")}</span>
      </button>
      <span class="map-hours">${d.hours}h</span>
    </div>`
    )
    .join("");
}

function bindMapActions() {
  modalBody.querySelectorAll("[data-travel]").forEach((b) => {
    b.addEventListener("click", () => {
      closeModal();
      submitAction(`go to ${b.dataset.travel}`);
    });
  });
}

const META_COMMANDS = new Set([
  "help", "?", "stats", "status", "sheet", "skills", "inventory", "inv",
  "goals", "objectives", "map", "where", "journal", "bonds", "relationships",
  "factions", "reputation", "guilds", "institutions", "lodge", "bounties",
  "bestiary", "case", "investigation", "routines", "schedule", "check",
]);

function isMetaCommand(text) {
  const first = text.toLowerCase().split(/\s+/)[0];
  if (META_COMMANDS.has(first)) return true;
  return /^(hints|equip|unequip|use)\s/i.test(text);
}

function updatePendingProse(text) {
  const el = document.querySelector("#pending-turn .turn-prose");
  if (!el) return;
  el.classList.remove("system");
  el.textContent = text;
}

async function submitActionStream(text) {
  const res = await fetch("/api/action/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(apiErrorDetail(data, res.statusText));
  }
  if (!res.body) {
    throw new Error("Streaming not supported in this browser.");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let streamed = "";
  let finalResult = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const msg = JSON.parse(line.slice(5).trim());
      if (msg.type === "chunk") {
        streamed += msg.text || "";
        updatePendingProse(streamed);
        scrollStoryToEnd();
      } else if (msg.type === "done") {
        finalResult = msg;
      } else if (msg.type === "error") {
        throw new Error(msg.detail || "Scene generation failed.");
      }
    }
  }

  if (!finalResult) {
    throw new Error("Stream ended without a final scene.");
  }
  applyResult(finalResult);
}

/* ── Actions ── */
function setBusy(on) {
  busy = on;
  actionInput.disabled = on;
  sendBtn.disabled = on;
  $("#app")?.classList.toggle("is-busy", on);
  updateSessionControls();
}

function refreshOpenModal() {
  if (openModalKind && !modal.classList.contains("hidden")) {
    openModal(openModalKind);
  }
}

function applyResult(result) {
  clearPending();
  if (result?.scene) {
    appendTurn(result.turn, result.scene, isMetaText(result.scene));
  }
  if (result?.turn) {
    renderDeltaPanel(result.turn);
  }
  if (result?.state) {
    state = result.state;
    try {
      renderStatusBar();
      renderSidebar();
      refreshOpenModal();
    } catch (err) {
      console.error("UI render failed:", err);
    }
  }
  renderChips(result?.action_hints || []);
  ensureSidebarVisible();
  syncLayoutMode();
}

function applyState(stateData) {
  if (!stateData) return;
  state = stateData;
  renderStatusBar();
  renderSidebar();
  syncLayoutMode();
}

async function submitAction(text) {
  if (busy || !text?.trim()) return;
  const trimmed = text.trim();
  setBusy(true);
  appendPending(trimmed);
  try {
    const useStream = !isMetaCommand(trimmed) && state?.session?.gemini_configured !== false;
    if (useStream) {
      await submitActionStream(trimmed);
    } else {
      const result = await api("/api/action", {
        method: "POST",
        body: JSON.stringify({ text: trimmed }),
      });
      if (!result?.scene) {
        clearPending();
        appendSystem("No scene text returned. Check GEMINI_API_KEY and server logs.");
      }
      applyResult(result);
    }
  } catch (err) {
    clearPending();
    appendSystem(err.message || String(err));
  } finally {
    setBusy(false);
    actionInput.focus({ preventScroll: true });
  }
}

async function startGame(result) {
  $("#boot")?.classList.add("hidden");
  $("#create-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  if (result?.state) {
    applyState(result.state);
    state = result.state;
  } else {
    state = await api("/api/state");
    applyState(state);
  }
  storyLog.innerHTML = "";
  renderDeltaPanel(null);
  if (result?.scene) {
    applyResult(result);
  } else {
    hydrateStoryHistory(state?.story_history || []);
    if (state?.player?.needs_opening) {
      setBusy(true);
      appendSystem("Opening the scene…");
      try {
        const open = await api("/api/opening", { method: "POST" });
        applyResult(open);
      } catch (err) {
        appendSystem("Opening failed: " + err.message);
      } finally {
        setBusy(false);
      }
    }
  }
  if (result?.message && !result?.scene) {
    appendSystem(result.message);
  }
  renderChips(result?.action_hints || []);
  scrollStoryToEnd();
  ensureSidebarVisible();
  syncLayoutMode();
  actionInput.focus({ preventScroll: true });
}

function showCreateScreen(setup) {
  $("#boot").classList.add("hidden");
  $("#create-screen").classList.remove("hidden");

  const lead = $("#create-lead");
  if (setup.starting_city) {
    lead.textContent = `You will arrive in ${setup.starting_city}.`;
  }
  if (!setup.gemini_configured) {
    $("#create-note").textContent =
      "Tip: add GEMINI_API_KEY to .env for the opening scene.";
  }

  const container = $("#c-backgrounds");
  container.innerHTML = "";
  (setup.backgrounds || []).forEach((bg, i) => {
    const label = document.createElement("label");
    label.className = "bg-option";
    label.innerHTML = `
      <input type="radio" name="background" value="${esc(bg.id)}" ${i === 0 ? "checked" : ""} />
      <span class="bg-label">${esc(bg.label)}</span>
      <span class="bg-desc">${esc(bg.description)}</span>
    `;
    container.appendChild(label);
  });
}

async function submitCharacter(e) {
  e.preventDefault();
  const btn = $("#create-btn");
  const note = $("#create-note");
  btn.disabled = true;
  note.textContent = "Creating your character and opening scene…";

  const bg = document.querySelector('input[name="background"]:checked');
  const payload = {
    name: $("#c-name").value.trim(),
    age: parseInt($("#c-age").value, 10) || 30,
    background: bg ? bg.value : "wanderer",
    appearance: $("#c-appearance").value.trim(),
    attire: $("#c-attire").value.trim(),
    motivation: $("#c-motivation").value.trim(),
  };

  try {
    const result = await api("/api/character", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await startGame(result);
  } catch (err) {
    note.textContent = err.message || String(err);
    btn.disabled = false;
  }
}

async function boot() {
  const bootEl = $("#boot");
  const bootMsg = $("#boot-msg");
  try {
    const health = await api("/api/health");
    if (!health.has_character) {
      const setup = await api("/api/setup");
      showCreateScreen(setup);
      return;
    }

    bootEl.classList.add("hidden");
    const data = await api("/api/state");
    await startGame({ state: data });
  } catch (err) {
    bootMsg.textContent = err.message || "Could not connect. Run: python api/server.py";
    bootEl.classList.add("error");
  }
}

$("#create-form")?.addEventListener("submit", submitCharacter);

actionForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const t = actionInput.value;
  actionInput.value = "";
  submitAction(t);
});

$("#modal-close").addEventListener("click", closeModal);
modalBackdrop.addEventListener("click", closeModal);
$("#btn-undo")?.addEventListener("click", undoLastTurn);

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && openModalKind) closeModal();
});

/* Mobile tabs — open modals / scroll sidebar; never hide sidebar */
const mobileTabs = $("#mobile-tabs");
mobileTabs?.querySelectorAll("button").forEach((btn) => {
  btn.addEventListener("click", () => {
    mobileTabs.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    const panel = btn.dataset.panel;
    document.body.classList.toggle("delta-drawer-open", panel === "aftermath");
    if (panel === "story") {
      storyLog?.scrollIntoView({ block: "start", behavior: "smooth" });
      return;
    }
    if (panel === "aftermath") {
      return;
    }
    if (panel === "sheets") {
      sidebar?.scrollIntoView({ block: "start", behavior: "smooth" });
      return;
    }
    if (panel === "more") {
      openModal("inventory");
      return;
    }
    if (panel === "character") openModal("character");
    if (panel === "relations") openModal("relations");
  });
});

initSidebar();
boot();
