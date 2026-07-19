# Helpdesk Pro

[![CI](https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/actions/workflows/ci.yml/badge.svg?branch=17.0)](https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro/actions/workflows/ci.yml)
[![License: LGPL-3](https://img.shields.io/badge/license-LGPL--3-blue.svg)](LICENSE)
[![Odoo](https://img.shields.io/badge/Odoo-17.0%20%7C%2019.0-714B67.svg)](https://www.odoo.com)

A free, production-grade helpdesk module for Odoo Community: SLA
tracking, a customer portal, CSAT ratings, canned responses, ticket
merging, and team analytics — all built on core Odoo (`mail`, `portal`,
`resource`), no third-party dependencies.

Maintained for **Odoo 17.0** (`17.0` branch) and **Odoo 19.0** (`19.0`
branch) in parallel.

## Features

- **SLA policies** — target resolution hours matched to a ticket by
  team, priority, and tag, with a live On Track / At Risk / Breached
  badge computed against the team's real working calendar (nights and
  weekends don't count).
- **Customer portal** — customers see only their own tickets, enforced
  by record rules (not a filtered view), with full communication
  history.
- **CSAT ratings** — one-click Good / Okay / Bad rating links emailed
  automatically when a ticket closes, secured with a signed,
  single-use token.
- **Canned responses** — reusable reply snippets, optionally scoped to
  a team, inserted into a ticket in one click.
- **Ticket merging** — fold a duplicate ticket's messages, followers,
  and attachments into the ticket you're keeping.
- **Email-to-ticket** — a team's email alias turns incoming mail into
  tickets automatically; replies thread back into the ticket either
  way.
- **Analytics** — pivot/graph ticket analysis plus per-team SLA
  compliance and average resolution stat buttons.
- **Demo data & i18n** — realistic demo dataset installs with the
  module; Arabic (`ar`) translation included alongside the English
  source strings.

See the [user guide](helpdesk_pro/docs/user-guide.md) (also available
[in Arabic](helpdesk_pro/docs/user-guide-ar.md)) for a full walkthrough.

## Install

1. Copy (or clone) the `helpdesk_pro/` folder into your Odoo addons
   path.
2. Restart Odoo and update the apps list.
3. Install **Helpdesk Pro** from Apps.

Requires only core Community apps as dependencies: `mail`, `portal`,
`resource`. No Enterprise features, no paid dependencies.

## Local development

Two independent Docker Compose stacks are provided, one per Odoo
series, each with its own Postgres volume and port:

```bash
docker compose -f docker-compose.yml up      # Odoo 17.0 → http://localhost:8069
docker compose -f docker-compose.19.yml up   # Odoo 19.0 → http://localhost:8079
```

Run the test suite inside a container:

```bash
docker compose run --rm web odoo -d test17 -i helpdesk_pro \
  --test-enable --test-tags /helpdesk_pro --stop-after-init
```

Lint before committing:

```bash
pre-commit run -a
```

## Contributing

Issues and pull requests are welcome. This project follows OCA-style
commit conventions and ships a `pre-commit` config
(`black`, `isort`, `flake8`, `pylint-odoo`) — please run it before
opening a PR.

## License

[LGPL-3](LICENSE)
