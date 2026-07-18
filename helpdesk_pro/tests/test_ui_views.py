"""UI smoke test: every Helpdesk view must open without a client-side error."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
import odoo.tests

from .common import make_mon_fri_calendar


@odoo.tests.tagged("post_install", "-at_install")
class TestHelpdeskUiViews(odoo.tests.HttpCase):
    """Click through every Helpdesk menu and view switch as admin.

    get_views() validates arch XML but never executes client-side OWL
    rendering, so a view that parses fine server-side can still throw at
    render time (this bit us on the 19.0 kanban port). This drives the real
    web client the way a user would and fails on any error dialog or JS
    error -- back-ported from 19.0 (PROJECT_BLUEPRINT.md §2) now that M3
    adds new views (SLA policy list/form, kanban SLA badges) needing the
    same coverage on 17.0.
    """

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """Grant admin manager rights so the crawl can reach every menu."""
        super().setUpClass()
        # A fresh admin has no helpdesk_pro group by default (same as any
        # real install): grant manager rights so the crawl can actually
        # reach every menu, including the manager-gated Configuration one.
        # PORT-19: groups_id -> group_ids.
        cls.env.ref("base.user_admin").groups_id = [
            (4, cls.env.ref("helpdesk_pro.group_helpdesk_manager").id)
        ]

    def test_click_everywhere_helpdesk(self):
        """Open every Helpdesk menu and switch every available view."""
        # PORT-19: start URL /web -> /odoo.
        self.browser_js(
            "/web",
            "odoo.loader.modules.get('@web/webclient/clickbot/clickbot_loader')"
            ".startClickEverywhere('helpdesk_pro.helpdesk_menu_root');",
            "odoo.isReady === true",
            login="admin",
            timeout=180,
            success_signal="clickbot test succeeded",
        )

    def test_ticket_form_shows_sla_fields(self):
        """A ticket with a matched SLA policy shows the SLA group on its
        form (sla_id/sla_deadline/sla_status) without a client-side error.

        The generic clickbot crawl above only exercises menus, filters and
        list/kanban view switches -- it never opens an individual record,
        so it can't catch a broken form arch (e.g. a bad invisible
        expression on the new SLA group). Opened directly via the action
        service, the same hook clickbot itself uses to reach app state.
        """
        calendar = make_mon_fri_calendar(self.env, name="SLA form check calendar")
        team = self.env["helpdesk.team"].create(
            {"name": "SLA Form Check", "calendar_id": calendar.id}
        )
        self.env["helpdesk.sla"].create(
            {"name": "Form check SLA", "team_id": team.id, "target_hours": 40}
        )
        ticket = self.env["helpdesk.ticket"].create(
            {"name": "SLA form check", "team_id": team.id}
        )
        self.assertTrue(ticket.sla_id)

        # PORT-19: start URL /web -> /odoo.
        self.browser_js(
            "/web",
            f"""
                (async () => {{
                    await odoo.__WOWL_DEBUG__.root.env.services.action.doAction({{
                        type: "ir.actions.act_window",
                        res_model: "helpdesk.ticket",
                        res_id: {ticket.id},
                        views: [[false, "form"]],
                    }});
                    await new Promise((r) => setTimeout(r, 500));
                    if (document.querySelector(".o_error_dialog")) {{
                        console.error("error dialog present on ticket form");
                        return;
                    }}
                    const slaField = '.o_field_widget[name="sla_status"]';
                    if (!document.querySelector(slaField)) {{
                        console.error("sla_status field not found on ticket form");
                        return;
                    }}
                    console.log("test successful");
                }})();
            """,
            "odoo.isReady === true",
            login="admin",
            timeout=60,
        )
