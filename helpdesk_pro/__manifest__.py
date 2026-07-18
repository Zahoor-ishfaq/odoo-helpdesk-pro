# pylint: disable=missing-module-docstring,pointless-statement
# Odoo loads this file via ast.literal_eval(), which requires the file to
# contain exactly one bare expression -- no docstring or other statement
# can precede the dict literal.
{
    "name": "Helpdesk Pro - SLA, Ratings & Email Support",
    "summary": "Enterprise-grade helpdesk: SLA engine, CSAT ratings, "
    "email-to-ticket, customer portal",
    "version": "17.0.1.0.0",
    "category": "Services/Helpdesk",
    "author": "Zahoor Ishfaq",
    "website": "https://github.com/Zahoor-ishfaq/odoo-helpdesk-pro",
    "license": "LGPL-3",
    "depends": ["mail", "portal", "resource"],
    "data": [
        "security/helpdesk_security.xml",
        "security/ir.model.access.csv",
        "data/helpdesk_stage_data.xml",
        "data/ir_sequence_data.xml",
        "data/mail_template_data.xml",
        "views/helpdesk_ticket_views.xml",
        "views/helpdesk_stage_views.xml",
        "views/helpdesk_tag_views.xml",
        "views/helpdesk_team_views.xml",
        "views/helpdesk_menus.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}
