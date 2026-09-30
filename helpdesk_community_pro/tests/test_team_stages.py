"""Tests for per-team stages (helpdesk.stage.team_ids)."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestHelpdeskTeamStages(TransactionCase):
    """Stages restricted to teams, shared stages, and moving between them."""

    @classmethod
    def setUpClass(cls):  # pylint: disable=invalid-name
        """Two teams; team A gets its own open and closed stage, placed
        before every stock (shared) stage so it becomes A's first stage."""
        super().setUpClass()
        cls.team_a = cls.env["helpdesk.team"].create({"name": "IT"})
        cls.team_b = cls.env["helpdesk.team"].create({"name": "Billing"})
        cls.a_open = cls.env["helpdesk.stage"].create(
            {"name": "IT Triage", "sequence": 1, "team_ids": [(6, 0, cls.team_a.ids)]}
        )
        cls.a_closed = cls.env["helpdesk.stage"].create(
            {
                "name": "IT Done",
                "sequence": 2,
                "is_closed": True,
                "team_ids": [(6, 0, cls.team_a.ids)],
            }
        )
        cls.shared_open = cls.env["helpdesk.stage"].search(
            [("team_ids", "=", False), ("is_closed", "=", False)], limit=1
        )
        cls.shared_closed = cls.env["helpdesk.stage"].search(
            [("team_ids", "=", False), ("is_closed", "=", True)], limit=1
        )

    def _ticket(self, team, **vals):
        return self.env["helpdesk.ticket"].create(
            {"name": "Team stage ticket", "team_id": team.id, **vals}
        )

    def test_shared_stage_available_to_every_team(self):
        """A stage with no teams can be used by any team."""
        for team in self.team_a | self.team_b:
            ticket = self._ticket(team, stage_id=self.shared_open.id)
            self.assertEqual(ticket.stage_id, self.shared_open)

    def test_restricted_stage_only_for_its_team(self):
        """Team A can use its own stage; team B is refused it."""
        ticket = self._ticket(self.team_a, stage_id=self.a_open.id)
        self.assertEqual(ticket.stage_id, self.a_open)
        with self.assertRaises(ValidationError):
            self._ticket(self.team_b, stage_id=self.a_open.id)
        ticket_b = self._ticket(self.team_b)
        with self.assertRaises(ValidationError):
            ticket_b.stage_id = self.a_open

    def test_default_stage_is_team_first_stage(self):
        """Without a stage_id, a ticket starts in its team's first stage."""
        self.assertEqual(self._ticket(self.team_a).stage_id, self.a_open)
        self.assertEqual(self._ticket(self.team_b).stage_id, self.shared_open)

    def test_default_stage_from_context_team(self):
        """The field default follows default_team_id (team-opened forms)."""
        ticket_model = self.env["helpdesk.ticket"]
        self.assertEqual(
            ticket_model.with_context(default_team_id=self.team_a.id)
            .default_get(["stage_id"])
            .get("stage_id"),
            self.a_open.id,
        )
        self.assertEqual(
            ticket_model.default_get(["stage_id"]).get("stage_id"),
            self.shared_open.id,
        )

    def test_team_change_moves_to_valid_stage(self):
        """Moving team A's ticket to team B leaves A's stages, keeping the
        open/closed state; a shared stage is simply kept."""
        ticket = self._ticket(self.team_a)
        self.assertEqual(ticket.stage_id, self.a_open)
        ticket.team_id = self.team_b
        self.assertEqual(ticket.stage_id, self.shared_open)

        closed = self._ticket(self.team_a)
        closed.stage_id = self.a_closed
        closed.team_id = self.team_b
        self.assertEqual(closed.stage_id, self.shared_closed)

        shared = self._ticket(self.team_b, stage_id=self.shared_open.id)
        shared.team_id = self.team_a
        self.assertEqual(shared.stage_id, self.shared_open)

    def test_team_change_onchange(self):
        """The form moves the stage as soon as the team changes."""
        with Form(self.env["helpdesk.ticket"]) as form:
            form.name = "Onchange"
            form.team_id = self.team_a
            self.assertEqual(form.stage_id, self.a_open)
            form.team_id = self.team_b
            self.assertEqual(form.stage_id, self.shared_open)
        ticket = form.save()

        # Saved ticket: a stage the new team can use is kept as is.
        ticket.stage_id = self.shared_closed
        with Form(ticket) as form:
            form.team_id = self.team_a
            self.assertEqual(form.stage_id, self.shared_closed)

    def test_kanban_columns_follow_context_team(self):
        """Grouping by stage from a team shows only that team's columns."""
        self._ticket(self.team_a)

        def columns(team=None):
            # Same domain + context as helpdesk.team.action_view_tickets.
            # (lazy read_group fills the group_expand columns on its own)
            ctx = {}
            domain = []
            if team:
                ctx["default_team_id"] = team.id
                domain = [("team_id", "=", team.id)]
            groups = (
                self.env["helpdesk.ticket"]
                .with_context(**ctx)
                .read_group(domain, ["stage_id"], ["stage_id"])
            )
            return {group["stage_id"][0] for group in groups if group["stage_id"]}

        team_b_columns = columns(self.team_b)
        self.assertNotIn(self.a_open.id, team_b_columns)
        self.assertIn(self.shared_open.id, team_b_columns)
        team_a_columns = columns(self.team_a)
        self.assertIn(self.a_open.id, team_a_columns)
        self.assertIn(self.shared_open.id, team_a_columns)
        self.assertIn(self.a_open.id, columns(), "no team: every stage")

    def test_reopen_lands_in_team_first_open_stage(self):
        """A customer reply reopens into the ticket team's own open stage."""
        ticket = self._ticket(self.team_a)
        ticket.stage_id = self.a_closed
        ticket.message_update({})
        self.assertEqual(ticket.stage_id, self.a_open)

        ticket_b = self._ticket(self.team_b)
        ticket_b.stage_id = self.shared_closed
        ticket_b.message_update({})
        self.assertEqual(ticket_b.stage_id, self.shared_open)
