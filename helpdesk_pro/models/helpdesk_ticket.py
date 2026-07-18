"""Helpdesk ticket: a single customer support request."""

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import api, fields, models


class HelpdeskTicket(models.Model):  # pylint: disable=too-few-public-methods
    """A customer support ticket moving through a team's stage pipeline."""

    _name = "helpdesk.ticket"
    _description = "Helpdesk Ticket"
    _inherit = ["mail.thread", "mail.activity.mixin", "portal.mixin"]
    _order = "priority desc, id desc"

    name = fields.Char(string="Subject", required=True, tracking=True)
    ref = fields.Char(default="New", readonly=True, copy=False)
    team_id = fields.Many2one("helpdesk.team", required=True, index=True, tracking=True)
    stage_id = fields.Many2one(
        "helpdesk.stage",
        required=True,
        index=True,
        tracking=True,
        default=lambda self: self.env["helpdesk.stage"].search(
            [], order="sequence", limit=1
        ),
        group_expand="_read_group_stage_ids",
    )
    user_id = fields.Many2one(
        "res.users", string="Assigned to", index=True, tracking=True
    )
    partner_id = fields.Many2one("res.partner", string="Customer", tracking=True)
    partner_email = fields.Char(string="Customer Email")
    partner_name = fields.Char(string="Customer Name")
    priority = fields.Selection(
        [
            ("0", "Low"),
            ("1", "Medium"),
            ("2", "High"),
            ("3", "Urgent"),
        ],
        default="1",
        required=True,
    )
    tag_ids = fields.Many2many("helpdesk.tag", string="Tags")
    description = fields.Html()
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    color = fields.Integer(string="Color Index", default=0)
    active = fields.Boolean(default=True)

    @api.model
    # PORT-19: group_expand callables are invoked with 2 args (records,
    # domain), not 3 (records, domain, order) as on 17.0 -- order is no
    # longer passed, so this relies on helpdesk.stage's own _order.
    def _read_group_stage_ids(self, stages, _domain):
        return stages.search([])

    @api.model_create_multi
    def create(self, vals_list):
        """Assign the next TKT/YYYY/NNNNN sequence value to new tickets."""
        for vals in vals_list:
            if vals.get("ref", "New") == "New":
                vals["ref"] = (
                    self.env["ir.sequence"].next_by_code("helpdesk.ticket") or "New"
                )
        return super().create(vals_list)
