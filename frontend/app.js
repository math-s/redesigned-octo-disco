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

function formatGoalTitle(goal) {
  const kind = String(goal.kind || "").toUpperCase();
  const target = Number(goal.target);
  if (kind === "BJJ_SESSIONS") return `BJJ sessions (${target})`;
  if (kind === "PILATES_SESSIONS") return `Pilates sessions (${target})`;
  if (kind === "MONEY_SAVED_CENTS") return `Money saved (${formatMoneyFromCents(target)})`;
  if (kind === "BOOKS_FINISHED") return `Books finished (${target})`;
  return goal.title || "Goal";
}

function getGoalProgressValue(goal, stats) {
  const kind = String(goal.kind || "").toUpperCase();
  if (kind === "BJJ_SESSIONS") return Number(stats?.bjjCount ?? 0);
  if (kind === "PILATES_SESSIONS") return Number(stats?.pilatesCount ?? 0);
  if (kind === "MONEY_SAVED_CENTS") return Number(stats?.savedCentsTotal ?? 0);
  if (kind === "BOOKS_FINISHED") return Number(stats?.readBooksTotal ?? 0);
  return null;
}

function formatGoalProgressValue(goal, value) {
  const kind = String(goal.kind || "").toUpperCase();
  if (kind === "MONEY_SAVED_CENTS") return formatMoneyFromCents(value);
  return String(value);
}

function daysLeftInYear(year) {
  const now = new Date();
  if (now.getFullYear() !== year) return null;
  const end = new Date(year, 11, 31, 23, 59, 59, 999);
  const ms = end.getTime() - now.getTime();
  if (!Number.isFinite(ms)) return null;
  const days = Math.ceil(ms / (24 * 60 * 60 * 1000));
  return Math.max(0, days);
}

function formatRateHints(goal, stats, year) {
  const target = typeof goal.target === "number" ? goal.target : null;
  const progressValue = getGoalProgressValue(goal, stats);
  if (target === null || progressValue === null) return "";
  if (!Number.isFinite(target) || !Number.isFinite(progressValue) || target <= 0) return "";

  const remaining = Math.max(0, target - progressValue);
  if (remaining <= 0) return `<div class="muted small">On pace: already at target.</div>`;

  const daysLeft = daysLeftInYear(year);
  if (daysLeft === null) return "";
  if (daysLeft === 0) return `<div class="muted small">EOY is here: ${escapeHtml(formatGoalProgressValue(goal, remaining))} remaining.</div>`;

  const perDay = remaining / daysLeft;
  const perWeek = perDay * 7;
  const perMonth = perDay * 30.4375; // avg days/month

  const kind = String(goal.kind || "").toUpperCase();
  if (kind === "MONEY_SAVED_CENTS") {
    return `<div class="muted small">To hit by Dec 31: ~${escapeHtml(formatMoneyFromCents(perWeek))}/week (or ~${escapeHtml(
      formatMoneyFromCents(perMonth),
    )}/month)</div>`;
  }

  // Count-based goals: show per-week (most intuitive), plus per-day for tight deadlines.
  const fmt = (n) => (n < 1 ? n.toFixed(2) : n < 10 ? n.toFixed(1) : String(Math.ceil(n)));
  const unit = kind === "BOOKS_FINISHED" ? "books" : "sessions";
  return `<div class="muted small">To hit by Dec 31: ~${escapeHtml(fmt(perWeek))} ${unit}/week (≈ ${escapeHtml(
    fmt(perDay),
  )}/${unit.slice(0, -1)}/day)</div>`;
}

function renderGoals(goals, stats) {
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
    const target = typeof g.target === "number" ? g.target : null;
    const progressValue = getGoalProgressValue(g, stats);
    const hasProgress = target !== null && progressValue !== null && Number.isFinite(progressValue) && target > 0;
    const pct = hasProgress ? Math.max(0, Math.min(100, Math.round((progressValue / target) * 100))) : null;
    const rateHints = hasProgress ? formatRateHints(g, stats, getSelectedYear()) : "";
    const progressHtml = hasProgress
      ? `
        <div class="progress">
          <div class="progress__meta">
            <span>${escapeHtml(formatGoalProgressValue(g, progressValue))} / ${escapeHtml(formatGoalProgressValue(g, target))}</span>
            <span>${pct}%</span>
          </div>
          <div class="progress__bar"><div class="progress__fill" style="width: ${pct}%"></div></div>
          ${rateHints}
        </div>
      `
      : "";
    el.innerHTML = `
      <div class="item__top">
        <div class="item__title">${escapeHtml(formatGoalTitle(g))}</div>
        <div class="item__meta"><span class="${tagClass}">${escapeHtml(g.status)}</span></div>
      </div>
      ${progressHtml}
      <div class="item__actions">
        <button class="btn btn--ghost" data-act="todo">Todo</button>
        <button class="btn btn--ghost" data-act="doing">Doing</button>
        <button class="btn btn--ghost" data-act="done">Done</button>
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
        : a.type === "PILATES"
          ? "Pilates session"
        : a.type === "SAVE"
          ? `Saved ${formatMoneyFromCents(a.amountCents)}`
          : a.type === "READ"
            ? `Finished${a.bookTitle ? ` • ${a.bookTitle}` : ""}${
                a.bookAuthors && a.bookAuthors.length ? ` • ${a.bookAuthors.join(", ")}` : ""
              }${a.isbn ? ` • ISBN ${a.isbn}` : ""}`
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
  $("statPilates").textContent = String(stats.pilatesCount ?? 0);
  $("statSaved").textContent = formatMoneyFromCents(stats.savedCentsTotal ?? 0);
  $("statRead").textContent = `${stats.readBooksTotal ?? 0} books • ${stats.readCount ?? 0} logs`;
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
    renderGoals(goalsRes.goals || [], statsRes.stats || {});
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

  // Default Pilates date to today (local).
  const pilatesDateEl = $("pilatesDate");
  if (pilatesDateEl) pilatesDateEl.value = toDateInputValue(new Date());

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
      setActionMsg(String(err.message || err));
    }
  });

  $("pilatesBtn").addEventListener("click", async () => {
    try {
      const parsed = parseDateInputValue($("pilatesDate")?.value);
      if (!parsed) throw new Error("Pick a valid Pilates date.");

      // Count it under the selected date's year (and switch the UI year if needed).
      const desiredYear = parsed.y;
      if (String(desiredYear) !== String(getSelectedYear())) {
        $("yearSelect").value = String(desiredYear);
      }

      // Use a midday local timestamp to avoid timezone shifting the date when displayed.
      const ts = `${parsed.v}T12:00:00`;

      setActionMsg("Recording Pilates…");
      await postAction("PILATES", { ts });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      setActionMsg(String(err.message || err));
    }
  });

  $("saveBtn").addEventListener("click", async () => {
    try {
      const raw = $("saveAmount")?.value ?? "";
      const v = Number(String(raw).trim());
      if (!Number.isFinite(v) || v < 0) throw new Error("Invalid amount");
      const amountCents = Math.round(v * 100);
      setActionMsg("Recording save…");
      await postAction("SAVE", { amountCents });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      setActionMsg(String(err.message || err));
    }
  });

  $("readBtn").addEventListener("click", async () => {
    try {
      const isbn = String($("readIsbn")?.value ?? "").trim();
      if (!isbn) throw new Error("ISBN is required.");
      setActionMsg("Looking up book…");
      await postAction("READ", { isbn });
      setActionMsg("Recorded.");
    } catch (err) {
      setActionMsg("");
      setActionMsg(String(err.message || err));
    }
  });

  $("clearRecentBtn").addEventListener("click", () => {
    $("actionsList").innerHTML = `<div class="muted small">Cleared (refresh to reload).</div>`;
  });

  $("addGoalBtn").addEventListener("click", async () => {
    try {
      const kind = String($("newGoalKind")?.value ?? "").trim();
      const targetRaw = String($("newGoalTarget")?.value ?? "").trim();
      if (!kind) throw new Error("Goal type is required.");
      if (!targetRaw) throw new Error("Target is required.");

      let target;
      if (kind === "MONEY_SAVED_CENTS") {
        const v = Number(targetRaw);
        if (!Number.isFinite(v) || v <= 0) throw new Error("Target must be > 0.");
        target = Math.round(v * 100);
      } else {
        const v = Number(targetRaw);
        if (!Number.isFinite(v) || v <= 0 || Math.floor(v) !== v) throw new Error("Target must be a positive integer.");
        target = v;
      }

      await api("/goals", { method: "POST", body: { year: getSelectedYear(), kind, target } });
      $("newGoalTarget").value = "";
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

