"""Helpdesk team: agent group that owns a queue of tickets."""

import ast

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import fields, models


class HelpdeskTeam(models.Model):  # pylint: disable=too-few-public-methods
    """A support team: members, working calendar and ticket queue."""

    _name = "helpdesk.team"
    _description = "Helpdesk Team"
    _inherit = ["mail.alias.mixin"]
    _order = "name"

    name = fields.Char(required=True, translate=True)
    alias_id = fields.Many2one(
        help="Incoming emails to this address become tickets for this "
        "team; replies thread into the ticket's chatter."
    )
    ticket_count = fields.Integer(compute="_compute_ticket_count")
    member_ids = fields.Many2many(
        "res.users",
        string="Team Members",
        domain=[("share", "=", False)],
    )
    calendar_id = fields.Many2one(
        "resource.calendar",
        string="Working Hours",
        required=True,
        default=lambda self: self.env.company.resource_calendar_id,
        help="Working calendar used to compute SLA deadlines for this team.",
    )
    color = fields.Integer(string="Color Index")
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    active = fields.Boolean(default=True)

    def _compute_ticket_count(self):
        # pylint: disable=protected-access
        data = self.env["helpdesk.ticket"]._read_group(
            [("team_id", "in", self.ids)], ["team_id"], ["__count"]
        )
        counts = {team.id: count for team, count in data}
        for team in self:
            team.ticket_count = counts.get(team.id, 0)

    def action_view_tickets(self):
        """Open this team's tickets, pre-filtered to this team."""
        self.ensure_one()
        # pylint: disable=protected-access
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "helpdesk_pro.helpdesk_ticket_action"
        )
        action["domain"] = [("team_id", "=", self.id)]
        action["context"] = {"default_team_id": self.id}
        return action

    def _alias_get_creation_values(self):
        """Route this team's alias to helpdesk.ticket, defaulting team_id."""
        values = super()._alias_get_creation_values()
        # pylint: disable=protected-access
        values["alias_model_id"] = self.env["ir.model"]._get("helpdesk.ticket").id
        if self.id:
            defaults = ast.literal_eval(self.alias_defaults or "{}")
            defaults["team_id"] = self.id
            values["alias_defaults"] = defaults
        return values
