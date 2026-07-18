from odoo import fields, models


class HelpdeskTag(models.Model):
    _name = "helpdesk.tag"
    _description = "Helpdesk Ticket Tag"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer(string="Color Index")

    _sql_constraints = [
        ("name_uniq", "unique (name)", "A tag with this name already exists."),
    ]
