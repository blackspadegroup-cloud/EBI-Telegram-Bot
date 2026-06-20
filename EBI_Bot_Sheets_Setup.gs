/**
 * EBI Bot Google Sheets Setup Script
 * ====================================
 * HOW TO USE:
 * 1. Go to: https://script.google.com
 * 2. Click "New Project"
 * 3. Delete all existing code and paste this entire file
 * 4. Click the floppy disk (Save), then click "Run"
 * 5. Approve permissions when asked (your Google account only)
 * 6. Both sheets will be created automatically in your Google Drive
 *    inside the folder: https://drive.google.com/drive/folders/1gQYADFyty15FsCg1Fq4UcSDSMqydNCYp
 *
 * This creates TWO spreadsheets:
 *   1. "EBI — New Member Tracker"
 *   2. "EBI — Admin Conversion Dashboard"
 */

// ── CONFIGURATION ─────────────────────────────────────────────────────────────

const FOLDER_ID = "1gQYADFyty15FsCg1Fq4UcSDSMqydNCYp";  // Your EBI folder

// ── COLOURS (EBI brand) ────────────────────────────────────────────────────────

const DARK_GOLD    = "#B8860B";
const LIGHT_GOLD   = "#FFF8DC";
const DARK_BG      = "#1A1A2E";
const WHITE        = "#FFFFFF";
const GREEN_LIGHT  = "#E8F5E9";
const AMBER_LIGHT  = "#FFF8E1";
const RED_LIGHT    = "#FFEBEE";
const GREY_HEADER  = "#F5F5F5";

// ── MAIN ENTRY POINT ──────────────────────────────────────────────────────────

function createAllSheets() {
  const folder = DriveApp.getFolderById(FOLDER_ID);
  createMemberTracker(folder);
  createConversionDashboard(folder);
  SpreadsheetApp.getUi().alert(
    "✅ Done!\n\nBoth spreadsheets have been created in your EBI Drive folder.\n\n" +
    "• EBI — New Member Tracker\n• EBI — Admin Conversion Dashboard"
  );
}

// ══════════════════════════════════════════════════════════════════════════════
// SHEET 1: NEW MEMBER TRACKER
// ══════════════════════════════════════════════════════════════════════════════

function createMemberTracker(folder) {
  const ss = SpreadsheetApp.create("EBI — New Member Tracker");
  DriveApp.getFileById(ss.getId()).moveTo(folder);

  const sheet = ss.getActiveSheet();
  sheet.setName("Members");

  // ── Headers ──────────────────────────────────────────────────────────────
  const headers = [
    "Date Joined",
    "Telegram ID",
    "Username",
    "First Name",
    "Last Name",
    "DM Welcomed",
    "Day 1 Sent",
    "Day 3 Sent",
    "Day 5 Sent",
    "Intent Score",
    "Top Intent Signal",
    "Follow-Up Status",
    "Converted?",
    "Notes",
    "Admin Assigned",
  ];

  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground(DARK_BG)
             .setFontColor(DARK_GOLD)
             .setFontWeight("bold")
             .setFontSize(11)
             .setHorizontalAlignment("center");

  // ── Column widths ─────────────────────────────────────────────────────────
  sheet.setColumnWidth(1, 120);   // Date Joined
  sheet.setColumnWidth(2, 130);   // Telegram ID
  sheet.setColumnWidth(3, 130);   // Username
  sheet.setColumnWidth(4, 120);   // First Name
  sheet.setColumnWidth(5, 120);   // Last Name
  sheet.setColumnWidth(6, 110);   // DM Welcomed
  sheet.setColumnWidth(7, 100);   // Day 1 Sent
  sheet.setColumnWidth(8, 100);   // Day 3 Sent
  sheet.setColumnWidth(9, 100);   // Day 5 Sent
  sheet.setColumnWidth(10, 110);  // Intent Score
  sheet.setColumnWidth(11, 180);  // Top Intent Signal
  sheet.setColumnWidth(12, 160);  // Follow-Up Status
  sheet.setColumnWidth(13, 110);  // Converted?
  sheet.setColumnWidth(14, 250);  // Notes
  sheet.setColumnWidth(15, 140);  // Admin Assigned

  // ── Data validation dropdowns ─────────────────────────────────────────────
  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["New", "Contacted", "Demo Opened", "Live Account", "Not Interested", "No Response"], true)
    .build();
  sheet.getRange(2, 12, 1000, 1).setDataValidation(statusRule);

  const convertedRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["No", "Demo", "Live", "Churned"], true)
    .build();
  sheet.getRange(2, 13, 1000, 1).setDataValidation(convertedRule);

  const yesNoRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Yes", "No", "Failed (Privacy)"], true)
    .build();
  sheet.getRange(2, 6, 1000, 1).setDataValidation(yesNoRule);
  sheet.getRange(2, 7, 1000, 1).setDataValidation(yesNoRule);
  sheet.getRange(2, 8, 1000, 1).setDataValidation(yesNoRule);
  sheet.getRange(2, 9, 1000, 1).setDataValidation(yesNoRule);

  // ── Conditional formatting ────────────────────────────────────────────────
  // Converted = Live → green
  const cfLive = sheet.getRange(2, 13, 1000, 1);
  const ruleLive = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Live")
    .setBackground(GREEN_LIGHT)
    .setFontColor("#1B5E20")
    .setFontWeight("bold")
    .setRanges([cfLive])
    .build();

  // Converted = Demo → amber
  const ruleDemo = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Demo")
    .setBackground(AMBER_LIGHT)
    .setFontColor("#E65100")
    .setRanges([cfLive])
    .build();

  // Follow-up = Contacted → light blue
  const cfStatus = sheet.getRange(2, 12, 1000, 1);
  const ruleContacted = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Contacted")
    .setBackground("#E3F2FD")
    .setFontColor("#0D47A1")
    .setRanges([cfStatus])
    .build();

  // High intent score (≥5) → amber
  const cfScore = sheet.getRange(2, 10, 1000, 1);
  const ruleHighIntent = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThanOrEqualTo(5)
    .setBackground(AMBER_LIGHT)
    .setFontColor("#E65100")
    .setFontWeight("bold")
    .setRanges([cfScore])
    .build();

  sheet.setConditionalFormatRules([ruleLive, ruleDemo, ruleContacted, ruleHighIntent]);

  // ── Sample data row ───────────────────────────────────────────────────────
  const sampleRow = [
    new Date(),           // Date Joined
    "123456789",          // Telegram ID
    "@sample_user",       // Username
    "John",               // First Name
    "Doe",                // Last Name
    "Yes",                // DM Welcomed
    "Yes",                // Day 1 Sent
    "No",                 // Day 3 Sent
    "No",                 // Day 5 Sent
    3,                    // Intent Score
    "Account Opening",    // Top Intent Signal
    "Contacted",          // Follow-Up Status
    "Demo",               // Converted?
    "Interested in Gold. Wants to start small.", // Notes
    "Steve",              // Admin Assigned
  ];
  sheet.getRange(2, 1, 1, headers.length).setValues([sampleRow]);
  sheet.getRange(2, 1, 1, headers.length).setBackground(LIGHT_GOLD);

  // ── Freeze header row + pin columns ──────────────────────────────────────
  sheet.setFrozenRows(1);
  sheet.setFrozenColumns(4);

  // ── Summary stats at the top right ───────────────────────────────────────
  const statsSheet = ss.insertSheet("Summary");
  _buildSummarySheet(statsSheet, "Members");

  // ── Auto filter ──────────────────────────────────────────────────────────
  sheet.getRange(1, 1, 1, headers.length).createFilter();

  Logger.log("✅ Member Tracker created: " + ss.getUrl());
}

function _buildSummarySheet(sheet, memberSheetName) {
  sheet.setName("Summary");

  const title = [["📊 EBI Member Tracker — Summary"]];
  sheet.getRange("A1").setValues(title);
  sheet.getRange("A1").setFontSize(16).setFontWeight("bold").setFontColor(DARK_GOLD);

  const stats = [
    ["Total Members", `=COUNTA('${memberSheetName}'!A2:A)`],
    ["", ""],
    ["✅ Converted to Live", `=COUNTIF('${memberSheetName}'!M2:M,"Live")`],
    ["📋 Demo Accounts", `=COUNTIF('${memberSheetName}'!M2:M,"Demo")`],
    ["📞 Contacted", `=COUNTIF('${memberSheetName}'!L2:L,"Contacted")`],
    ["🆕 New (Not Contacted)", `=COUNTIF('${memberSheetName}'!L2:L,"New")`],
    ["", ""],
    ["🎯 High Intent (Score ≥5)", `=COUNTIF('${memberSheetName}'!J2:J,">="&5)`],
    ["📬 DM Welcomed", `=COUNTIF('${memberSheetName}'!F2:F,"Yes")`],
    ["📧 Day 5 Sent", `=COUNTIF('${memberSheetName}'!I2:I,"Yes")`],
    ["", ""],
    ["📈 Conversion Rate", `=IFERROR(TEXT(COUNTIF('${memberSheetName}'!M2:M,"Live")/COUNTA('${memberSheetName}'!A2:A),"0.0%"),"N/A")`],
  ];

  sheet.getRange(3, 1, stats.length, 2).setValues(stats);
  sheet.getRange(3, 1, stats.length, 1).setFontWeight("bold");
  sheet.getRange(3, 2, stats.length, 1).setHorizontalAlignment("center");
  sheet.setColumnWidth(1, 220);
  sheet.setColumnWidth(2, 120);
}


// ══════════════════════════════════════════════════════════════════════════════
// SHEET 2: ADMIN CONVERSION DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════

function createConversionDashboard(folder) {
  const ss = SpreadsheetApp.create("EBI — Admin Conversion Dashboard");
  DriveApp.getFileById(ss.getId()).moveTo(folder);

  // ── TAB 1: Intent Pipeline ─────────────────────────────────────────────────
  const pipelineSheet = ss.getActiveSheet();
  pipelineSheet.setName("🎯 Intent Pipeline");
  _buildPipelineSheet(pipelineSheet);

  // ── TAB 2: Weekly Engagement Log ──────────────────────────────────────────
  const engSheet = ss.insertSheet("📅 Engagement Log");
  _buildEngagementSheet(engSheet);

  // ── TAB 3: Admin Activity ─────────────────────────────────────────────────
  const adminSheet = ss.insertSheet("👤 Admin Activity");
  _buildAdminSheet(adminSheet);

  // ── TAB 4: KPI Scorecard ──────────────────────────────────────────────────
  const kpiSheet = ss.insertSheet("📊 KPI Scorecard");
  _buildKpiSheet(kpiSheet);

  Logger.log("✅ Conversion Dashboard created: " + ss.getUrl());
}

function _buildPipelineSheet(sheet) {
  const headers = [
    "Date",
    "Telegram ID",
    "Username",
    "First Name",
    "Intent Signal",
    "Their Question",
    "Cumulative Score",
    "Status",
    "Admin Follow-Up",
    "Follow-Up Date",
    "Outcome",
    "Notes",
  ];

  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground(DARK_BG).setFontColor(DARK_GOLD).setFontWeight("bold")
             .setFontSize(11).setHorizontalAlignment("center");

  // Column widths
  const widths = [110, 130, 130, 120, 160, 320, 130, 140, 140, 130, 140, 250];
  widths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));

  // Dropdowns
  const statusRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["New Alert", "Admin Assigned", "In Conversation", "Demo Opened", "Live Account", "Not Interested", "No Response"], true)
    .build();
  sheet.getRange(2, 8, 500, 1).setDataValidation(statusRule);

  const outcomeRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Pending", "Demo", "Live Account", "Not Interested", "Ghost"], true)
    .build();
  sheet.getRange(2, 11, 500, 1).setDataValidation(outcomeRule);

  // Conditional formatting — hot leads
  const cfScore = sheet.getRange(2, 7, 500, 1);
  const ruleHot = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThanOrEqualTo(6)
    .setBackground("#FFCCCC").setFontColor("#B71C1C").setFontWeight("bold")
    .setRanges([cfScore]).build();
  const ruleWarm = SpreadsheetApp.newConditionalFormatRule()
    .whenNumberBetween(3, 5)
    .setBackground(AMBER_LIGHT).setFontColor("#E65100")
    .setRanges([cfScore]).build();

  const cfStatus = sheet.getRange(2, 8, 500, 1);
  const ruleLive = SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo("Live Account")
    .setBackground(GREEN_LIGHT).setFontColor("#1B5E20").setFontWeight("bold")
    .setRanges([cfStatus]).build();

  sheet.setConditionalFormatRules([ruleHot, ruleWarm, ruleLive]);
  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, headers.length).createFilter();

  // Sample row
  const sample = [
    new Date(), "987654321", "@john_trader", "John",
    "Account Opening", "How do I open a trading account for Gold?",
    5, "Admin Assigned", "Steve", new Date(), "Pending", "Very interested, will follow up tomorrow"
  ];
  sheet.getRange(2, 1, 1, headers.length).setValues([sample]);
  sheet.getRange(2, 1, 1, headers.length).setBackground(AMBER_LIGHT);
}

function _buildEngagementSheet(sheet) {
  const headers = [
    "Date",
    "Content Type",
    "Title",
    "Approved By",
    "Posted Time",
    "Reactions Count",
    "Comments / Replies",
    "Notes",
  ];

  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground(DARK_BG).setFontColor(DARK_GOLD).setFontWeight("bold")
             .setFontSize(11).setHorizontalAlignment("center");

  const widths = [110, 160, 220, 130, 130, 130, 160, 250];
  widths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));

  const typeRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Monday Outlook", "Wednesday Tip", "Friday Review", "Weekend Mindset", "Poll", "Announcement", "Broadcast"], true)
    .build();
  sheet.getRange(2, 2, 200, 1).setDataValidation(typeRule);

  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, headers.length).createFilter();
}

function _buildAdminSheet(sheet) {
  const headers = [
    "Date",
    "Admin Name",
    "Action",
    "Target User",
    "Telegram ID",
    "Outcome",
    "Time Spent (min)",
    "Notes",
  ];

  const headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground(DARK_BG).setFontColor(DARK_GOLD).setFontWeight("bold")
             .setFontSize(11).setHorizontalAlignment("center");

  const widths = [110, 130, 180, 150, 130, 160, 140, 250];
  widths.forEach((w, i) => sheet.setColumnWidth(i + 1, w));

  const actionRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["Follow-Up DM", "Group Reply", "Demo Setup", "Account Assist", "Complaint Handle", "Onboarding Call", "Other"], true)
    .build();
  sheet.getRange(2, 3, 200, 1).setDataValidation(actionRule);

  sheet.setFrozenRows(1);
  sheet.getRange(1, 1, 1, headers.length).createFilter();
}

function _buildKpiSheet(sheet) {
  sheet.getRange("A1").setValue("📊 EBI Bot KPI Scorecard");
  sheet.getRange("A1").setFontSize(18).setFontWeight("bold").setFontColor(DARK_GOLD);
  sheet.getRange("A2").setValue("Update this sheet manually each week or month.");
  sheet.getRange("A2").setFontColor("#888888").setFontStyle("italic");

  const kpiHeaders = ["KPI", "This Week", "Last Week", "This Month", "Target", "Status"];
  sheet.getRange(4, 1, 1, 6).setValues([kpiHeaders]);
  sheet.getRange(4, 1, 1, 6)
    .setBackground(DARK_BG).setFontColor(DARK_GOLD).setFontWeight("bold")
    .setHorizontalAlignment("center");

  const kpis = [
    ["New Members Joined", "", "", "", "20", ""],
    ["DM Welcome Sent", "", "", "", "20", ""],
    ["Day 5 Sequence Sent", "", "", "", "15", ""],
    ["Intent Alerts Generated", "", "", "", "10", ""],
    ["Admins Followed Up", "", "", "", "10", ""],
    ["Demo Accounts Opened", "", "", "", "5", ""],
    ["Live Accounts Converted", "", "", "", "2", ""],
    ["Re-engagement DMs Sent", "", "", "", "20", ""],
    ["30-Day Milestone DMs Sent", "", "", "", "", ""],
    ["Polls Posted", "", "", "", "1/week", ""],
    ["Weekly Content Posted", "", "", "", "4/week", ""],
    ["Bot Uptime %", "", "", "", "99%", ""],
  ];

  sheet.getRange(5, 1, kpis.length, 6).setValues(kpis);

  // Alternating row colors
  for (let i = 0; i < kpis.length; i++) {
    const bg = i % 2 === 0 ? WHITE : GREY_HEADER;
    sheet.getRange(5 + i, 1, 1, 6).setBackground(bg);
  }

  // Bold KPI names
  sheet.getRange(5, 1, kpis.length, 1).setFontWeight("bold");

  // Column widths
  sheet.setColumnWidth(1, 240);
  sheet.setColumnWidth(2, 110);
  sheet.setColumnWidth(3, 110);
  sheet.setColumnWidth(4, 110);
  sheet.setColumnWidth(5, 100);
  sheet.setColumnWidth(6, 100);

  sheet.setFrozenRows(4);
}
