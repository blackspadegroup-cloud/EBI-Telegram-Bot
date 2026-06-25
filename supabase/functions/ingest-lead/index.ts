// Supabase Edge Function: ingest-lead
// Universal lead-capture endpoint. Any source (website form, Meta/TikTok via Zapier,
// Telegram) POSTs a lead here. Auto-scores, de-duplicates (email / telegram_id),
// and creates or merges a row in crm_leads. Uses the service role (bypasses RLS).
//
// Auth: a public CAPTURE_TOKEN (not a secret key) + a honeypot field. Worst case of
// leakage is spam leads, never data exposure. Deployed with verify_jwt = false so a
// public website form can POST without a Supabase JWT.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CAPTURE_TOKEN = "ebi_cap_7q2m9x4k1f3v";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(obj: unknown, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { ...cors, "content-type": "application/json" },
  });
}

function scoreFor(source: string, hasExperience: boolean): number {
  const base: Record<string, number> = {
    "referral": 70, "webinar": 60, "web form": 40, "whatsapp": 45,
    "meta": 40, "tiktok": 35, "instagram": 35, "manual": 30,
  };
  let s = base[source] ?? 30;
  if (hasExperience) s += 10;
  return Math.min(100, s);
}

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "method not allowed" }, 405);

  let body: Record<string, unknown> = {};
  try { body = await req.json(); } catch { return json({ error: "bad json" }, 400); }

  // Honeypot: real users leave it empty; bots fill it. Silently accept + ignore.
  if (body.hp) return json({ ok: true });
  if (body.token !== CAPTURE_TOKEN) return json({ error: "unauthorized" }, 401);

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
  );

  const email = String(body.email ?? "").trim().toLowerCase();
  const phone = String(body.phone ?? "").trim();
  const tg = body.telegram_id ? Number(body.telegram_id) : null;
  const source = String(body.source ?? "web form");
  const dedupe = (email || (tg ? "tg:" + tg : "") || phone).toLowerCase();
  const score = scoreFor(source, !!body.experience);

  // De-dupe by email or telegram_id
  let existing: { id: number; score: number } | null = null;
  const ors: string[] = [];
  if (email) ors.push(`email.eq.${email}`);
  if (tg) ors.push(`telegram_id.eq.${tg}`);
  if (ors.length) {
    const { data } = await supabase.from("crm_leads").select("id,score").or(ors.join(",")).limit(1);
    existing = data && data[0] ? data[0] : null;
  }

  if (existing) {
    await supabase.from("crm_leads").update({
      last_activity_at: new Date().toISOString(),
      score: Math.max(existing.score ?? 0, score),
    }).eq("id", existing.id);
    await supabase.from("crm_activities").insert({
      lead_id: existing.id, type: "signal", summary: `New submission via ${source}`, actor: "capture",
    });
    return json({ ok: true, deduped: true, id: existing.id });
  }

  const { data: ins, error } = await supabase.from("crm_leads").insert({
    full_name: body.full_name ?? body.name ?? null,
    email: email || null,
    phone: phone || null,
    country: body.country ?? null,
    language: body.language ?? null,
    source,
    campaign: body.campaign ?? null,
    telegram_id: tg,
    score,
    stage: "new",
    status: "new",
    dedupe_hash: dedupe || null,
    notes: body.notes ?? body.experience ?? null,
    created_by: "capture",
  }).select("id").single();

  if (error) return json({ error: error.message }, 500);

  await supabase.from("crm_activities").insert({
    lead_id: ins.id, type: "created", summary: `Lead captured via ${source}`, actor: "capture",
  });
  return json({ ok: true, id: ins.id });
});
