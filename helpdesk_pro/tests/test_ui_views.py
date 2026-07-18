"""UI smoke test: every Helpdesk view must open without a client-side error."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
import odoo.tests


@odoo.tests.tagged("post_install", "-at_install")
class TestHelpdeskUiViews(
    odoo.tests.HttpCase
):  # pylint: disable=too-few-public-methods
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
