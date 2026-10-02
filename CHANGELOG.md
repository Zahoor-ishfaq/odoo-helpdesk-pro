# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versions follow Odoo's `<series>.<major>.<minor>.<patch>.<build>` tagging
convention (e.g. `v17.0.1.0.0`), tagged separately per supported series.

## [1.1.0] - 2026-10-02

Tagged as `v17.0.1.1.0` and `v19.0.1.1.0`.

### Fixed

- **CSAT ratings recorded by email link scanners** — the rating links in
  the CSAT email now open a confirmation page and only record the
  rating when the customer presses **Submit** (a POST that re-checks the
  token, value and update window). Previously a plain GET recorded it,
  so mail security scanners (Safe Links, Mimecast, Proofpoint, ...)
  could record ratings the customer never gave.
- **Stage email templates were never sent** — a stage's **Email
  Template** is now posted to the ticket's chatter (and emailed to the
  customer) whenever a ticket moves into that stage. Merging tickets
  doesn't trigger it.
- **Crash when an SLA calendar can't place a deadline** — a matched SLA
  policy on a calendar with no working hours no longer breaks ticket
  creation, closing, or the SLA cron; the ticket gets no SLA status and
  a warning is logged for the admin.
- **Reopened tickets kept stale close/SLA data** — reopening a ticket
  now clears its close date and "SLA reached" flag (so team analytics
  stop counting it as closed) and refreshes its SLA status and open
  hours immediately. The SLA deadline stays anchored to creation; a
  re-close is judged against it.
- **Docs: CSAT links are not single-use** — the 1.0.0 notes, README and
  Apps Store description called the rating token "single-use". It is a
  signed per-ticket link that the customer can use to change their
  rating for 7 days; the docs now say so.

### Changed

- **Per-team stages** — stages have a new **Teams** field. A stage with
  no teams is shared by every team (all existing stages, so existing
  pipelines are unchanged); one with teams is only offered to them. New
  tickets start in their team's first stage, kanban columns opened from
  a team show only its stages, changing a ticket's team moves it to a
  valid stage, and customer replies reopen into the ticket team's first
  open stage.

## [1.0.0] - 2026-07-19

Initial release. Supports Odoo 17.0 and 19.0 in parallel, tagged
separately as `v17.0.1.0.0` and `v19.0.1.0.0`.

### Added

- **Tickets & pipeline** — `helpdesk.ticket` with subject, description,
  customer, assignee, team, priority, tags, and a configurable
  `helpdesk.stage` pipeline with closing-stage marking.
- **Teams** — `helpdesk.team` with members, a working-hours calendar,
  and an inbound email alias (`mail.alias.mixin`).
- **Email-to-ticket** — incoming mail to a team's alias creates a
  ticket automatically; replies from either side thread into the same
  record.
- **SLA engine** — `helpdesk.sla` policies matched by team, priority,
  and tag; calendar-aware deadline, open-hours, and resolution-hours
  computation; On Track / At Risk / Breached status shown as a badge
  on the kanban card, list, search filters, and ticket form; a
  background cron keeps status current on open tickets.
- **Customer portal** — a "My Tickets" list and per-ticket detail page
  under the standard portal, access-controlled by record rules (not a
  filtered view), with reply-via-chatter support.
- **CSAT ratings** — a Good / Okay / Bad rating email sent on ticket
  close (per-team opt-in), secured by a signed, single-use HMAC token;
  ratings roll up into a per-team average.
- **Canned responses** — reusable reply snippets, optionally scoped to
  a team, inserted into a ticket via a preview wizard.
- **Ticket merging** — fold a duplicate ticket's messages, followers,
  and attachments into the ticket being kept, with a back-reference
  left on the closed duplicate.
- **Analytics** — pivot/graph "Ticket Analysis" view, plus per-team SLA
  compliance and average resolution stat buttons.
- **Demo data** — a realistic set of teams, SLA policies, canned
  responses, and tickets (open, in-progress, and closed/rated) for
  evaluating the module without configuring it first.
- **i18n** — full `.pot` translation template and an Arabic (`ar`)
  translation.
- **Docs** — public README, an EN/AR user guide, and a dev-only
  real-email (Gmail IMAP/SMTP) setup guide.
- **Security** — `User: Agent` and `Manager` groups, multi-company
  record rules, and portal record rules scoping customers to their own
  tickets.
- **CI** — GitHub Actions lint (`pre-commit`) and test matrix against
  both `odoo:17.0` and `odoo:19.0` images, including a browser-based
  (`clickbot`) UI regression pass.

[1.1.0]: https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/releases/tag/v17.0.1.1.0
[v19.0.1.1.0]: https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/releases/tag/v19.0.1.1.0
[1.0.0]: https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/releases/tag/v17.0.1.0.0
[v19.0.1.0.0]: https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/releases/tag/v19.0.1.0.0
