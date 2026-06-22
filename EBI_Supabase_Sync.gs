// ============================================================
// EBI — Supabase → Google Sheets Sync  (v2)
// Pulls live bot data from Supabase every 15 minutes.
//
// SETUP (one-time):
//   1. Open the Member Tracker sheet → Extensions → Apps Script
//   2. Replace the whole script with this file, click Save
//   3. Run setupTrigger() ONCE (authorise when prompted)
//   4. Data now syncs every 15 minutes automatically
//
// Tabs written:
//   • Member Tracker → "Members"
//   • Dashboard      → "Intent Pipeline"   (full event feed, read-only)
//   • Dashboard      → "Potential Clients"  (1 row per lead, manual columns kept)
// ============================================================

// ── Project: "The Trading Terminal" (the project the bot actually writes to) ──
const SUPABASE_URL = "https://jnyzkukhrwgiaqqtwfvv.supabase.co";
// Service-role key (read-only use here). Internal script only — keep private.
const SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpueXprdWtocndnaWFxcXR3ZnZ2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4MTM3ODIzNiwiZXhwIjoyMDk2OTU0MjM2fQ.JM8dEmWBNfvKUQQDVHrOPR2je5yzz8hMnrjnb1-Di20";

const MEMBER_TRACKER_ID = "1VqSxg87nGjxxmbPVnJDjguKAP0Yd5q76FxSsOj0_cVo";
const DASHBOARD_ID      = "1wsjSGOKC67mJf0fqxZU81cO6LptQ-Co_g8uQuIGz1pk";

const HOT_SCORE = 3;          // score at/above this = highlight as a hot lead
const NAVY = "#1F2A44";
const HOT  = "#FCE8E6";

// ── REST helper ───────────────────────────────────────────────
function supabaseFetch(table, params) {
  const query = params ? "?" + params : "";
  const res = UrlFetchApp.fetch(`${SUPABASE_URL}/rest/v1/${table}${query}`, {
    headers: {
      "apikey": SUPABASE_KEY,
      "Authorization": "Bearer " + SUPABASE_KEY,
      "Content-Type": "application/json",
    },
    muteHttpExceptions: true,
  });
  if (res.getResponseCode() !== 200) {
    Logger.log(`Supabase error on ${table}: ${res.getContentText()}`);
    return [];
  }
  return JSON.parse(res.getContentText());
}

// ── Master ────────────────────────────────────────────────────
function syncAll() {
  const events = supabaseFetch("bot_intent_events", "order=created_at.asc&limit=5000");
  syncMembers(events);
  syncIntentPipeline(events);
  syncPotentialClients(events);
  Logger.log("✅ EBI sync complete: " + new Date().toISOString());
}

// Build a per-member aggregate from intent events.
function aggregateLeads(events) {
  const map = {};
  events.forEach(e => {
    const id = String(e.telegram_id || "");
    if (!id) return;
    if (!map[id]) map[id] = { id, first: e.created_at, last: e.created_at, score: 0,
      count: 0, username: "", name: "", signal: "", question: "" };
    const m = map[id];
    m.score += (e.score_delta || 0);
    m.count += 1;
    m.last = e.created_at;                         // events are ascending → last wins
    if (e.intent_label) m.signal = e.intent_label; // latest non-empty label
    if (e.question) m.question = e.question;
    if (e.username) m.username = e.username;
    if (e.first_name) m.name = e.first_name;
  });
  return map;
}

// ── 1. Members tab (preserves manual columns L–O) ─────────────
function syncMembers(events) {
  const rows = supabaseFetch("telegram_subscribers", "order=joined_at.desc&limit=2000");
  if (!rows.length) { Logger.log("No members found"); return; }

  const leads = aggregateLeads(events || supabaseFetch("bot_intent_events", "limit=5000"));

  // onboarding step per member (bot_state key onboarding_step:{id})
  const steps = {};
  supabaseFetch("bot_state", "key=like.onboarding_step:*&limit=5000").forEach(s => {
    const id = String(s.key).split(":")[1];
    steps[id] = Number(s.value) || 0;
  });

  const sheet = SpreadsheetApp.openById(MEMBER_TRACKER_ID).getSheetByName("Members");
  const manual = readManual(sheet, 2, [12, 13, 14, 15]);   // keyed by Telegram ID (col 2)

  const data = rows.map(r => {
    const id = String(r.chat_id || "");
    const lead = leads[id] || {};
    const step = steps[id] || 0;
    const m = manual[id] || {};
    return [
      r.joined_at ? new Date(r.joined_at) : (r.first_seen ? new Date(r.first_seen) : ""),
      r.chat_id || "",
      r.username ? "@" + r.username : "",
      r.first_name || "",
      "",                              // last name (not collected)
      "Yes",                           // DM Welcomed (welcomed on join)
      step >= 1 ? "Yes" : "",
      step >= 3 ? "Yes" : "",
      step >= 5 ? "Yes" : "",
      lead.score || 0,
      lead.signal || "",
      m[12] || "",                     // Follow-Up Status (manual, preserved)
      m[13] || "",                     // Converted? (manual)
      m[14] || "",                     // Notes (manual)
      m[15] || "",                     // Admin Assigned (manual)
    ];
  });

  writeBlock(sheet, data, 15);
}

// ── 2. Intent Pipeline tab (full event feed, newest first) ────
function syncIntentPipeline(events) {
  const evs = (events || supabaseFetch("bot_intent_events", "limit=5000"))
    .slice().sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 1000);
  if (!evs.length) { Logger.log("No intent events"); return; }

  const sheet = SpreadsheetApp.openById(DASHBOARD_ID).getSheetByName("Intent Pipeline");
  if (!sheet) { Logger.log("Intent Pipeline tab missing"); return; }

  const data = evs.map(e => [
    e.created_at ? new Date(e.created_at) : "",
    e.telegram_id || "",
    e.username ? "@" + e.username : "",
    e.first_name || "",
    e.intent_label || "",
    e.question || "",
    e.score_delta || 0,
    "", "", "", "", "",   // Status / Admin / Follow-Up Date / Outcome / Notes (manual feed)
  ]);
  writeBlock(sheet, data, 12);
}

// ── 3. Potential Clients tab (1 row per lead, manual cols kept) ─
function syncPotentialClients(events) {
  const map = aggregateLeads(events || supabaseFetch("bot_intent_events", "limit=5000"));
  const leads = Object.keys(map).map(k => map[k]).sort((a, b) => b.score - a.score);

  const ss = SpreadsheetApp.openById(DASHBOARD_ID);
  let sheet = ss.getSheetByName("Potential Clients");
  const header = ["First Seen", "Last Activity", "Telegram ID", "Username", "Name",
    "Total Score", "Top Signal", "Latest Message", "# Signals", "DM Link",
    "Status", "Admin", "Outcome", "Notes"];
  if (!sheet) {
    sheet = ss.insertSheet("Potential Clients", 0);
    sheet.appendRow(header);
    sheet.getRange(1, 1, 1, header.length).setFontWeight("bold")
      .setFontColor("#FFFFFF").setBackground(NAVY);
    sheet.setFrozenRows(1);
  }

  const manual = readManual(sheet, 3, [11, 12, 13, 14]);   // keyed by Telegram ID (col 3)

  const data = leads.map(l => {
    const m = manual[String(l.id)] || {};
    const link = l.username ? "https://t.me/" + l.username : "tg://user?id=" + l.id;
    return [
      new Date(l.first), new Date(l.last), l.id, l.username ? "@" + l.username : "", l.name,
      l.score, l.signal, l.question, l.count, link,
      m[11] || "", m[12] || "", m[13] || "", m[14] || "",
    ];
  });

  writeBlock(sheet, data, 14);

  // Highlight hot leads (score >= HOT_SCORE)
  if (data.length) {
    const scores = sheet.getRange(2, 6, data.length, 1).getValues();
    for (let i = 0; i < data.length; i++) {
      const bg = (scores[i][0] >= HOT_SCORE) ? HOT : "#FFFFFF";
      sheet.getRange(i + 2, 1, 1, 14).setBackground(bg);
    }
    sheet.getRange(2, 1, data.length, 2).setNumberFormat("dd/MM/yyyy HH:mm");
  }
}

// ── Helpers ───────────────────────────────────────────────────

// Read manual columns into a map keyed by the value in column `keyCol`.
function readManual(sheet, keyCol, cols) {
  const out = {};
  if (!sheet) return out;
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return out;
  const width = sheet.getLastColumn();
  const vals = sheet.getRange(2, 1, lastRow - 1, width).getValues();
  vals.forEach(r => {
    const key = String(r[keyCol - 1]);
    if (!key) return;
    const rec = {};
    cols.forEach(c => rec[c] = r[c - 1]);
    out[key] = rec;
  });
  return out;
}

// Clear old data rows (keep header) and write the new block.
function writeBlock(sheet, data, width) {
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, width).clearContent();
  if (data.length) {
    sheet.getRange(2, 1, data.length, width).setValues(data);
    sheet.getRange(2, 1, data.length, 1).setNumberFormat("dd/MM/yyyy HH:mm");
  }
}

// ── Setup / test ──────────────────────────────────────────────
function setupTrigger() {
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "syncAll") ScriptApp.deleteTrigger(t);
  });
  ScriptApp.newTrigger("syncAll").timeBased().everyMinutes(15).create();
  Logger.log("✅ Trigger created — syncAll runs every 15 minutes");
  syncAll();
}

function testConnection() {
  Logger.log("Members sample: " + JSON.stringify(supabaseFetch("telegram_subscribers", "limit=2")));
  Logger.log("Events sample: " + JSON.stringify(supabaseFetch("bot_intent_events", "limit=3")));
}
