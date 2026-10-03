"""Helpdesk stage: kanban pipeline step for tickets."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import api, fields, models


class HelpdeskStage(models.Model):  # pylint: disable=too-few-public-methods
    """A kanban pipeline stage, shared by all teams or restricted to some."""

    _name = "helpdesk.stage"
    _description = "Helpdesk Stage"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(
        string="Folded in Kanban",
        help="This stage is folded in the kanban view when there are no "
        "records to display in it.",
    )
    is_closed = fields.Boolean(
        string="Closing Stage",
        help="Tickets in this stage are considered closed.",
    )
    mail_template_id = fields.Many2one(
        "mail.template",
        string="Email Template",
        help="Email automatically sent to the customer when a ticket "
        "moves into this stage from another one. Tickets created directly "
        "in this stage don't receive it.",
    )
    team_ids = fields.Many2many(
        "helpdesk.team",
        string="Teams",
        help="Teams using this stage. Leave empty to share it with all teams.",
    )

    @api.model
    def _get_team_stages_domain(self, team):
        """Domain of the stages available to `team`: its own plus shared ones.

        Empty team_ids means "shared by every team" rather than "used by
        none", so databases from before per-team stages existed -- where no
        stage has any team -- keep one pipeline for everyone unchanged.
        """
        return ["|", ("team_ids", "=", False), ("team_ids", "in", team.ids)]

    @api.model
    def _get_team_first_stage(self, team, is_closed=None):
        """First stage (by sequence) available to `team`, optionally the
        first with the given is_closed value."""
        domain = self._get_team_stages_domain(team)
        if is_closed is not None:
            domain = domain + [("is_closed", "=", is_closed)]
        return self.search(domain, limit=1)
