/* global window, document, fetch */

// 1) Set this after deploying the backend (SAM output "ApiUrl")
// Example: https://abc123.execute-api.us-east-1.amazonaws.com
const API_BASE_URL = "https://yfbupzcfla.execute-api.us-east-1.amazonaws.com";
// Optional: change to "BRL", "USD", "EUR", etc.
const MONEY_CURRENCY = "BRL";

const STORAGE_TOKEN_KEY = "yeargoals_admin_token";

function $(id) {
  return document.getElementById(id);
}

function formatMoneyFromCents(cents) {
  const v = Number(cents || 0) / 100;
  return new Intl.NumberFormat(undefined, { style: "currency", currency: MONEY_CURRENCY }).format(v);
}

function formatIso(ts) {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch {
    return String(ts);
  }
}

function getToken() {
  return window.localStorage.getItem(STORAGE_TOKEN_KEY) || "";
}

function setToken(token) {
  window.localStorage.setItem(STORAGE_TOKEN_KEY, token);
}

function clearToken() {
  window.localStorage.removeItem(STORAGE_TOKEN_KEY);
}

async function api(path, { method = "GET", body } = {}) {
  if (!API_BASE_URL || API_BASE_URL.includes("REPLACE_WITH")) {
    throw new Error("API_BASE_URL is not set in frontend/app.js");
  }
  const headers = { "content-type": "application/json" };
  const token = getToken();
  if (token) headers["x-admin-token"] = token;

  const res = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data && data.error ? data.error : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

function yearFromUrl() {
  const u = new URL(window.location.href);
  const v = u.searchParams.get("year");
  const y = Number(v || "");
  if (!Number.isFinite(y) || y < 1970 || y > 3000) return new Date().getFullYear();
  return y;
}

function setYearInUrl(year) {
  const u = new URL(window.location.href);
  u.searchParams.set("year", String(year));
  window.history.replaceState({}, "", u.toString());
}

function setAuthPanelVisible(visible) {
  $("authPanel").classList.toggle("hidden", !visible);
}

function setAuthError(msg) {
  const el = $("authError");
  el.textContent = msg || "";
  el.classList.toggle("hidden", !msg);
}

function setActionMsg(msg) {
  $("actionMsg").textContent = msg || "";
}

function toDateInputValue(d) {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

function parseDateInputValue(value) {
  const v = String(value || "").trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) return null;
  const y = Number(v.slice(0, 4));
  const m = Number(v.slice(5, 7));
  const d = Number(v.slice(8, 10));
  if (!Number.isFinite(y) || !Number.isFinite(m) || !Number.isFinite(d)) return null;
  if (y < 1970 || y > 3000) return null;
  if (m < 1 || m > 12) return null;
  if (d < 1 || d > 31) return null;
  return { y, v };
}

function renderGoals(goals) {
  const root = $("goalsList");
  root.innerHTML = "";

  if (!goals.length) {
    root.innerHTML = `<div class="muted small">No goals yet for this year.</div>`;
    return;
  }

  for (const g of goals) {
    const el = document.createElement("div");
    el.className = "item";

    const tagClass = g.status === "done" ? "tag tag--done" : g.status === "doing" ? "tag tag--doing" : "tag";
    el.innerHTML = `
      <div class="item__top">
        <div class="item__title">${escapeHtml(g.title)}</div>
        <div class="item__meta"><span class="${tagClass}">${escapeHtml(g.status)}</span></div>
      </div>
      <div class="item__actions">
        <button class="btn btn--ghost" data-act="todo">Todo</button>
        <button class="btn btn--ghost" data-act="doing">Doing</button>
        <button class="btn btn--ghost" data-act="done">Done</button>
        <button class="btn btn--ghost" data-act="edit">Edit</button>
        <button class="btn btn--ghost" data-act="del">Delete</button>
      </div>
    `;

    el.addEventListener("click", async (e) => {
      const btn = e.target.closest("button");
      if (!btn) return;
      const act = btn.getAttribute("data-act");
      if (!act) return;

      const year = getSelectedYear();

      try {
        if (act === "del") {
          if (!window.confirm("Delete this goal?")) return;
          await api(`/goals/${encodeURIComponent(g.id)}?year=${year}`, { method: "DELETE" });
          await refreshAll();
          return;
        }
        if (act === "edit") {
          const title = window.prompt("Edit goal title:", g.title);
          if (title === null) return;
          await api(`/goals/${encodeURIComponent(g.id)}`, { method: "PATCH", body: { year, patch: { title } } });
          await refreshAll();
          return;
        }
        if (act === "todo" || act === "doing" || act === "done") {
          await api(`/goals/${encodeURIComponent(g.id)}`, { method: "PATCH", body: { year, patch: { status: act } } });
          await refreshAll();
          return;
        }
      } catch (err) {
        window.alert(String(err.message || err));
      }
    });

    root.appendChild(el);
  }
}

function renderActions(actions) {
  const root = $("actionsList");
  root.innerHTML = "";

  if (!actions.length) {
    root.innerHTML = `<div class="muted small">No actions yet. Use the buttons above.</div>`;
    return;
  }

  for (const a of actions) {
    const title =
      a.type === "BJJ"
        ? "BJJ session"
        : a.type === "SAVE"
          ? `Saved ${formatMoneyFromCents(a.amountCents)}`
          : a.type === "READ"
            ? `Reading${a.pages ? ` • ${a.pages} pages` : ""}${a.book ? ` • ${a.book}` : ""}`
            : a.type;

    const meta = formatIso(a.ts);
    const note = a.note ? `<div class="muted small">${escapeHtml(a.note)}</div>` : "";

    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `
      <div class="item__top">
        <div class="item__title">${escapeHtml(title)}</div>
        <div class="item__meta">${escapeHtml(meta)}</div>
      </div>
      ${note}
    `;
    root.appendChild(el);
  }
}

function renderStats(stats) {
  $("statBjj").textContent = String(stats.bjjCount ?? 0);
  $("statSaved").textContent = formatMoneyFromCents(stats.savedCentsTotal ?? 0);
  $("statRead").textContent = `${stats.readPagesTotal ?? 0} pages • ${stats.readCount ?? 0} logs`;
  $("statsMeta").textContent = stats.updatedAt ? `Updated ${formatIso(stats.updatedAt)}` : "";
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => {
    switch (c) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#039;";
      default:
        return c;
    }
  });
}

function getSelectedYear() {
  const y = Number($("yearSelect").value);
  return Number.isFinite(y) ? y : new Date().getFullYear();
}

function populateYears(selectedYear) {
  const sel = $("yearSelect");
  sel.innerHTML = "";
  const thisYear = new Date().getFullYear();
  for (let y = thisYear + 1; y >= 1970; y--) {
    const opt = document.createElement("option");
    opt.value = String(y);
    opt.textContent = String(y);
    if (y === selectedYear) opt.selected = true;
    sel.appendChild(opt);
  }
}

async function refreshAll() {
  const year = getSelectedYear();
  setYearInUrl(year);
  $("apiBaseLabel").textContent = API_BASE_URL;

  setActionMsg("");
  setAuthError("");

  try {
    const [statsRes, goalsRes, actionsRes] = await Promise.all([
      api(`/stats?year=${year}`),
      api(`/goals?year=${year}`),
      api(`/actions?year=${year}&limit=30`),
    ]);
    renderStats(statsRes.stats || {});
    renderGoals(goalsRes.goals || []);
    renderActions(actionsRes.actions || []);
    setAuthPanelVisible(false);
  } catch (err) {
    // Most common: missing/invalid token
    setAuthPanelVisible(true);
    setAuthError(String(err.message || err));
  }
}

async function postAction(type, extra) {
  const year = getSelectedYear();
  await api("/actions", { method: "POST", body: { year, type, ...extra } });
  await refreshAll();
}

async function init() {
  const initialYear = yearFromUrl();
  populateYears(initialYear);

  // Default BJJ date to today (local).
  const bjjDateEl = $("bjjDate");
  if (bjjDateEl) bjjDateEl.value = toDateInputValue(new Date());

  $("yearSelect").addEventListener("change", refreshAll);
  $("refreshBtn").addEventListener("click", refreshAll);
  $("lockBtn").addEventListener("click", () => {
    clearToken();
    setAuthPanelVisible(true);
    setAuthError("Locked. Paste token to continue.");
  });

  $("saveTokenBtn").addEventListener("click", async () => {
    const token = $("tokenInput").value.trim();
    if (!token) {
      setAuthError("Token is required.");
      return;
    }
    setToken(token);
    $("tokenInput").value = "";
    await refreshAll();
  });

  $("bjjBtn").addEventListener("click", async () => {
    try {
      const parsed = parseDateInputValue($("bjjDate")?.value);
      if (!parsed) throw new Error("Pick a valid BJJ date.");

      // Count it under the selected date's year (and switch the UI year if needed).
      const desiredYear = parsed.y;
      if (String(desiredYear) !== String(getSelectedYear())) {
        $("yearSelect").value = String(desiredYear);
      }

      // Use a midday local timestamp to avoid timezone shifting the date when displayed.
      const ts = `${parsed.v}T12:00:00`;

      setActionMsg("Recording BJJ…");
      await postAction("BJJ", { ts });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      window.alert(String(err.message || err));
    }
  });

  $("saveBtn").addEventListener("click", async () => {
    try {
      const amount = window.prompt("How much did you save? (e.g. 12.34)");
      if (amount === null) return;
      const v = Number(amount);
      if (!Number.isFinite(v) || v < 0) throw new Error("Invalid amount");
      const amountCents = Math.round(v * 100);
      setActionMsg("Recording save…");
      await postAction("SAVE", { amountCents });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      window.alert(String(err.message || err));
    }
  });

  $("readBtn").addEventListener("click", async () => {
    try {
      const pagesRaw = window.prompt("Pages read? (integer; optional)", "0");
      if (pagesRaw === null) return;
      const pages = Number(pagesRaw);
      if (!Number.isFinite(pages) || pages < 0 || Math.floor(pages) !== pages) throw new Error("Invalid pages");
      const book = window.prompt("Book name? (optional)", "");
      setActionMsg("Recording reading…");
      await postAction("READ", { pages: pages, book: (book || "").trim() || undefined });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      window.alert(String(err.message || err));
    }
  });

  $("clearRecentBtn").addEventListener("click", () => {
    $("actionsList").innerHTML = `<div class="muted small">Cleared (refresh to reload).</div>`;
  });

  $("addGoalBtn").addEventListener("click", async () => {
    const title = $("newGoalTitle").value.trim();
    if (!title) return;
    try {
      await api("/goals", { method: "POST", body: { year: getSelectedYear(), title } });
      $("newGoalTitle").value = "";
      await refreshAll();
    } catch (err) {
      window.alert(String(err.message || err));
    }
  });

  // First load
  if (getToken()) setAuthPanelVisible(false);
  else setAuthPanelVisible(true);
  await refreshAll();
}

init().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  setAuthPanelVisible(true);
  setAuthError(String(err.message || err));
});

