"""Helpdesk ticket: a single customer support request."""

import logging

# pylint: disable=import-error
# odoo is not installed in the isolated pylint-odoo pre-commit environment.
from odoo import _, api, fields, models
from odoo.tools.mail import email_split_tuples

_logger = logging.getLogger(__name__)


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

    @api.model
    def message_new(self, msg_dict, custom_values=None):
        """Create a ticket from an inbound email (see mail.thread).

        team_id comes from the alias's own defaults (helpdesk.team's
        _alias_get_creation_values), not from anything parsed here.
        """
        defaults = dict(custom_values or {})
        defaults.setdefault("name", msg_dict.get("subject") or _("No Subject"))
        defaults.setdefault("description", msg_dict.get("body"))
        # pylint: disable=broad-except
        # Inbound mail must never crash the gateway: any unexpected shape
        # here (missing/garbled headers) falls back to a bare ticket.
        try:
            email_from = msg_dict.get("email_from") or ""
            pairs = email_split_tuples(email_from)
            name, email = pairs[0] if pairs else ("", email_from)
            defaults.setdefault("partner_email", email)
            defaults.setdefault("partner_name", name or email)
            if msg_dict.get("author_id"):
                defaults.setdefault("partner_id", msg_dict["author_id"])
        except Exception:
            _logger.warning(
                "helpdesk: could not parse sender %r on inbound email %r, "
                "falling back to a bare ticket",
                msg_dict.get("email_from"),
                msg_dict.get("message_id"),
                exc_info=True,
            )
        ticket = super().message_new(msg_dict, custom_values=defaults)
        ticket._send_ack_email()  # pylint: disable=protected-access
        return ticket

    def message_update(self, msg_dict, update_vals=None):
        """Reopen a closed ticket when the customer replies (see mail.thread).

        Threading the reply into the chatter itself is already handled by
        the mail gateway (message_post, called separately by
        _message_route_process) -- this only needs the reopen side effect.
        """
        open_stage = self.env["helpdesk.stage"].search(
            [("is_closed", "=", False)], order="sequence", limit=1
        )
        for ticket in self:
            if ticket.stage_id.is_closed and open_stage:
                ticket.stage_id = open_stage
        return super().message_update(msg_dict, update_vals=update_vals)

    def _send_ack_email(self):
        """Queue the "ticket received" acknowledgement for email-created tickets."""
        self.ensure_one()
        if not self.partner_email:
            return
        template = self.env.ref(
            "helpdesk_pro.mail_template_ticket_received", raise_if_not_found=False
        )
        if template:
            template.send_mail(self.id, force_send=False)
