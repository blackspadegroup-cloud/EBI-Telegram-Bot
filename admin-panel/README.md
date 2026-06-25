# EBI Admin Panel — deploy guide

A no-build static app (`index.html`) — no npm, no compiler. It talks to your Supabase
("Elite By Infinity") using the **publishable** key, which is safe to ship in the browser:
all access is enforced by Row-Level Security in the database, not by hiding the key.

## What it does (first slice)
- Email + password login, with "First time? Set password" and "Forgot password?"
  (sends a reset email). A one-time email link is kept as a quiet fallback.
- Role detection from `bot_panel_users` (Steve = admin, team = editors)
- Content editor: edit any message, **Submit for review** (creates a pending version)
- Approvals (admin only): **Approve & publish** / **Reject** pending submissions
- Day/night theme toggle
- Settings, Intent rules, FAQ, CRM, Sent log, Education = next slice

## One-time setup (all free)

1. **Supabase → Authentication → Providers:** make sure **Email** is enabled.
   - "Confirm email" ON (recommended) = a new user clicks one confirmation email the first
     time they set a password. OFF = password works immediately (slightly less strict).
     Either way, day-to-day login is just email + password, no link.
2. **Supabase → Authentication → URL Configuration → Redirect URLs:** add your panel URLs
   (the temporary `https://<project>.pages.dev` and later `https://admin.elitesbyinfinity.com`).
   Password-reset and confirmation links redirect back here, so these must be allow-listed.
3. **Cloudflare Pages → Create project → Connect to Git →** pick the bot repo.
   - Framework preset: **None**
   - Build command: *(leave empty)*
   - Build output directory: **admin-panel**
   - Deploy. You'll get a free `https://<project>.pages.dev` URL to test on.
4. **Test:** open the pages.dev URL, log in with `blackspadegroup@gmail.com`, approve a test edit.

## Go live (last step, no rush)
- Cloudflare Pages → your project → **Custom domains** → add `admin.elitesbyinfinity.com`.
- Add the DNS record Cloudflare shows you (a CNAME) at wherever elitesbyinfinity.com's DNS lives.
- Add `https://admin.elitesbyinfinity.com` to the Supabase redirect URLs (step 2).

## Add a team editor
Either: panel (later, once the Users screen ships), or one row in Supabase:
`insert into bot_panel_users (email, role, display_name) values ('teammate@email.com','editor','Name');`
