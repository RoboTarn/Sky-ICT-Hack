# Verification / 12 October 2026

- Python/API/optimizer: **30 tests passed**, including automatic drafts, due-time activation, refusal replanning, stale results, no feasible plan and lease expiry.
- Production build: passed; lazy routes and self-hosted Thai fonts.
- Local full workflow: incident automatically drafts without analysis button → commander approval → A21 handoff → A09/A17 travel → checklists → completion → resolved.
- Typhoon: actual API selected a validated plan during local flow and during hosted emergency flow.
- Local cross-window mission update: **119 ms**; hosted Commander → Crew across the two custom domains: **820 ms** in the measured browser run.
- Forecast before/after: **3 → 1** predicted late tasks in the main synthetic scenario.
- Commander, Crew, emergency dialog and crew entry: root width matched **320, 375, 414, 768 and 1536 px**. No unnamed visible controls in the core flow.
- axe WCAG AA: no application violations on all four surfaces. Only empty Fluent/Tabster focus-management sentinels are excluded. Loading spinners have accessible names.
- Visible keyboard focus, Escape dismissal, acknowledgment retained through refresh, reduced motion, crew search/selection and no browser page exceptions passed.
- Cloud persistence: tested two independent Engine instances and a fresh cold-start instance against the real Neon store; shared snapshots, single analysis lease, duplicate-approval transaction, missions and play state survived.
- Vercel production build deployed successfully; both custom domain configurations were verified. Added only the two requested CNAME records in Hostinger, TTL 300.
- Hosted browser: both root routes, crew selection, auto drafting, approval, cross-domain crew acceptance, fire popup and actual `TYPHOON / LIVE` explanation passed. Reset the shared demo afterward.
- Credentials: `.env` remains Git-ignored and excluded from upload; configured key absent from frontend build assets and local server logs. Cloud key stored as a server-side Secret.

Reproduce local checks with `npm run test`, `npm run build`, `npm run test:browser` and `npm run test:ui` while the dev server runs. `scripts/hosted-check.js` drives the deployed demo through Chrome; it resets the shared world. Screenshots are under `output/playwright/`.

This is a public synthetic demo with simulated crew identity and a shared simulation round. Local persistence uses SQLite/SSE; Vercel uses Neon Postgres and 1.2-second browser polling. Airport integrations, real GPS and external emergency notifications are outside this prototype. Windows Node exited unexpectedly once during local verification; restarting the dev server restored it, and the Linux Vercel builds succeeded.
