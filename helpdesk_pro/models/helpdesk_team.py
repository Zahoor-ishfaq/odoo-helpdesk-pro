from odoo import fields, models


class HelpdeskTeam(models.Model):
    _name = "helpdesk.team"
    _description = "Helpdesk Team"
    _order = "name"

    name = fields.Char(required=True, translate=True)
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
