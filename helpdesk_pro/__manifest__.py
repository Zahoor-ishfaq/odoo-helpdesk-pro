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
    ],
    "demo": [],
    "installable": True,
    "application": True,
}
