# Lead capture — website wiring & test

**Endpoint (live):** `https://jnyzkukhrwgiaqqtwfvv.supabase.co/functions/v1/ingest-lead`
**Capture token:** `ebi_cap_7q2m9x4k1f3v`

This token is a *public capture key* — it's meant to live in your website's code. It can only
*create leads*, never read data, so the worst case if someone copies it is spam leads (the
honeypot field below blocks bots). It is NOT a secret like your database keys.

## 1. Quick live test (do this first — 5 seconds)

Open your site, press F12 → Console, paste this, hit Enter:

```js
fetch("https://jnyzkukhrwgiaqqtwfvv.supabase.co/functions/v1/ingest-lead", {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ token: "ebi_cap_7q2m9x4k1f3v", full_name: "Console Test",
    email: "consoletest@example.com", source: "web form", experience: "beginner" })
}).then(r => r.json()).then(console.log)
```

You should see `{ ok: true, id: ... }`. Open the CRM → Leads and you'll see "Console Test."
(Delete that test lead afterward.) Run it again — the response says `deduped: true` and no
second lead appears. That confirms capture + de-dupe.

## 2. Wire your masterclass form

In your site's "Reserve Free Seat" form, after the user submits, send the fields to the
endpoint. Map your fields → these names: `full_name`, `phone`, `email`, `country`,
`experience`. Keep the hidden `hp` field empty (it's a bot trap).

```html
<!-- hidden honeypot field somewhere in the form -->
<input type="text" name="hp" style="display:none" tabindex="-1" autocomplete="off">
```

```js
async function sendLeadToCRM(form) {
  await fetch("https://jnyzkukhrwgiaqqtwfvv.supabase.co/functions/v1/ingest-lead", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      token: "ebi_cap_7q2m9x4k1f3v",
      source: "web form",
      full_name: form.fullName.value,
      phone:     form.phone.value,
      email:     form.email.value,
      experience: form.experience ? form.experience.value : "",
      hp:        form.hp ? form.hp.value : "",
      campaign:  new URLSearchParams(location.search).get("utm_campaign") || ""
    })
  });
}
```

Whoever maintains elitesbyinfinity.com adds this call to the form's submit handler. It runs
*alongside* your existing "You're on the list!" confirmation — it doesn't replace it.

## 3. YouTube / organic social

These don't submit forms. Put your masterclass link in the video/bio with a UTM tag
(e.g. `?utm_campaign=youtube`) — the form capture above reads it into the lead's `campaign`,
so you still see "where did this lead come from."

## 4. Facebook / Instagram / TikTok lead ads (later)

Same endpoint. Connect Meta/TikTok Lead Ads → Zapier (or Make) → "Webhook POST" to this URL,
mapping the ad-form fields to the names above, with `source: "meta"` / `"tiktok"`. Needs your
ad-platform accounts; flagged to set up later.
