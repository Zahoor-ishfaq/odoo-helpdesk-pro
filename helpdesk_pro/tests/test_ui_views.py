"""UI smoke test: every Helpdesk view must open without a client-side error."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
import odoo.tests


@odoo.tests.tagged("post_install", "-at_install")
class TestHelpdeskUiViews(
    odoo.tests.HttpCase
):  # pylint: disable=too-few-public-methods
    """Click through every Helpdesk menu and view switch as admin.

    Regression test for the 19.0 kanban port: get_views() validates arch
    XML but never executes client-side OWL rendering, so a mismatched
    kanban template name (kanban-box vs card) passed server-side install
    and only surfaced as a browser OwlError. This drives the real web
    client the way a user would and fails on any error dialog or JS error.
    """

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """Grant admin manager rights so the crawl can reach every menu."""
        super().setUpClass()
        # A fresh admin has no helpdesk_pro group by default (same as any
        # real install): grant manager rights so the crawl can actually
        # reach every menu, including the manager-gated Configuration one.
        cls.env.ref("base.user_admin").group_ids = [
            (4, cls.env.ref("helpdesk_pro.group_helpdesk_manager").id)
        ]

    def test_click_everywhere_helpdesk(self):
        """Open every Helpdesk menu and switch every available view."""
        self.browser_js(
            "/odoo",
            "odoo.loader.modules.get('@web/webclient/clickbot/clickbot_loader')"
            ".startClickEverywhere('helpdesk_pro.helpdesk_menu_root');",
            "odoo.isReady === true",
            login="admin",
            timeout=180,
            success_signal="clickbot test succeeded",
        )
