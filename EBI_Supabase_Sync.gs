// ============================================================
// EBI — Supabase → Google Sheets Sync
// Pulls data from Supabase every 15 minutes via time trigger.
//
// SETUP INSTRUCTIONS (one-time):
//   1. Paste this entire script into your Apps Script editor
//      (either the Member Tracker or a new standalone script)
//   2. Click Save, then run setupTrigger() ONCE
//   3. That's it — data syncs every 15 minutes automatically
// ============================================================

const SUPABASE_URL  = "https://gnxdbwsgfhttsbfiizrw.supabase.co";
const SUPABASE_KEY  = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImdueGRid3NnZmh0dHNiZmlpenJ3Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODE3NzE3MDIsImV4cCI6MjA5NzM0NzcwMn0.zlhCO_v_F0AfHis5xoaPnGQYIoraarR1PqfxLirSr9c";

// Spreadsheet IDs from your Drive
const MEMBER_TRACKER_ID  = "1VqSxg87nGjxxmbPVnJDjguKAP0Yd5q76FxSsOj0_cVo";
const DASHBOARD_ID       = "1wsjSGOKC67mJf0fqxZU81cO6LptQ-Co_g8uQuIGz1pk";

// ── Header styles ─────────────────────────────────────────────
const DARK_BG    = "#1A1A2E";
const DARK_GOLD  = "#B8860B";

// ── Supabase REST helper ──────────────────────────────────────
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

// ── Main sync function (runs every 15 min) ────────────────────
function syncAll() {
  syncMembers();
  syncIntentPipeline();
  Logger.log("✅ EBI sync complete: " + new Date().toISOString());
}

// ── 1. Sync telegram_subscribers → Member Tracker ─────────────
function syncMembers() {
  const rows = supabaseFetch(
    "telegram_subscribers",
    "order=joined_at.desc&limit=1000"
  );
  if (!rows.length) { Logger.log("No members found"); return; }

  const ss    = SpreadsheetApp.openById(MEMBER_TRACKER_ID);
  const sheet = ss.getSheetByName("Members");

  // Clear existing data (keep header row)
  const lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, 15).clearContent();

  // Map Supabase columns → sheet columns
  const data = rows.map(r => [
    r.joined_at  ? new Date(r.joined_at)  : "",
    r.chat_id    || "",
    r.username   ? "@" + r.username : "",
    r.first_name || "",
    r.last_name  || "",
    r.welcomed   ? "Yes" : "No",
    r.onboarding_day1_sent ? "Yes" : "No",
    r.onboarding_day3_sent ? "Yes" : "No",
    r.onboarding_day5_sent ? "Yes" : "No",
    "",   // Intent Score — filled from intent table
    "",   // Top Intent Signal — filled from intent table
    "",   // Follow-Up Status — manual
    "",   // Converted? — manual
    "",   // Notes — manual
    "",   // Admin Assigned — manual
  ]);

  if (data.length) {
    sheet.getRange(2, 1, data.length, 15).setValues(data);
    // Format date column
    sheet.getRange(2, 1, data.length, 1)
      .setNumberFormat("dd/MM/yyyy HH:mm");
  }

  // Overlay intent score + top signal from bot_intent_events
  _overlayIntentScores(sheet, rows);

  Logger.log(`Synced ${rows.length} members`);
}

// Helper: overlay the latest intent score per user onto Members tab
function _overlayIntentScores(sheet, members) {
  const events = supabaseFetch(
    "bot_intent_events",
    "order=created_at.desc&limit=2000"
  );
  if (!events.length) return;

  // Build map: chat_id → { score, signal }
  const scoreMap = {};
  events.forEach(e => {
    const id = String(e.chat_id || e.user_id || "");
    if (!scoreMap[id]) {
      scoreMap[id] = { score: e.intent_score || 0, signal: e.intent_type || e.intent || "" };
    }
    // accumulate total score per user
    scoreMap[id].score += (e.intent_score || 0);
  });

  // Write back into col J (score) and K (signal)
  members.forEach((m, i) => {
    const id = String(m.chat_id || "");
    if (scoreMap[id]) {
      const row = i + 2;
      sheet.getRange(row, 10).setValue(scoreMap[id].score);
      sheet.getRange(row, 11).setValue(scoreMap[id].signal);
    }
  });
}

// ── 2. Sync bot_intent_events → Dashboard Intent Pipeline tab ──
function syncIntentPipeline() {
  const events = supabaseFetch(
    "bot_intent_events",
    "order=created_at.desc&limit=500"
  );
  if (!events.length) { Logger.log("No intent events found"); return; }

  const ss    = SpreadsheetApp.openById(DASHBOARD_ID);
  const sheet = ss.getSheetByName("Intent Pipeline");
  if (!sheet) { Logger.log("Intent Pipeline tab not found in Dashboard"); return; }

  const lastRow = sheet.getLastRow();
  if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, 12).clearContent();

  const data = events.map(e => [
    e.created_at ? new Date(e.created_at) : "",
    e.chat_id    || e.user_id || "",
    e.username   ? "@" + e.username : "",
    e.first_name || "",
    e.intent_type || e.intent || "",
    e.message_text || e.message || "",
    e.intent_score || 0,
    "",   // Status — manual
    "",   // Admin — manual
    "",   // Follow-Up Date — manual
    "",   // Outcome — manual
    "",   // Notes — manual
  ]);

  if (data.length) {
    sheet.getRange(2, 1, data.length, 12).setValues(data);
    sheet.getRange(2, 1, data.length, 1).setNumberFormat("dd/MM/yyyy HH:mm");
  }

  Logger.log(`Synced ${events.length} intent events`);
}

// ── Setup: run this ONCE to create the 15-min trigger ─────────
function setupTrigger() {
  // Remove any existing sync triggers first
  ScriptApp.getProjectTriggers().forEach(t => {
    if (t.getHandlerFunction() === "syncAll") {
      ScriptApp.deleteTrigger(t);
    }
  });

  ScriptApp.newTrigger("syncAll")
    .timeBased()
    .everyMinutes(15)
    .create();

  Logger.log("✅ Trigger created — syncAll will run every 15 minutes");
  SpreadsheetApp.getUi
    ? Logger.log("Trigger active.")
    : null;

  // Run immediately so team sees data right away
  syncAll();
}

// ── Manual test: run this to check connection ──────────────────
function testConnection() {
  const rows = supabaseFetch("telegram_subscribers", "limit=3");
  Logger.log("Sample members: " + JSON.stringify(rows, null, 2));
  const events = supabaseFetch("bot_intent_events", "limit=3");
  Logger.log("Sample intent events: " + JSON.stringify(events, null, 2));
}
