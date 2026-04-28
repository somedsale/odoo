# -*- coding: utf-8 -*-
{
    "name": "Mailbox Client",
    "version": "17.0.2.0.0",
    "summary": "Mailbox client in Odoo using IMAP/SMTP",
    "description": """
Mailbox Client
==============
- Manage mailbox accounts
- Fetch emails from IMAP
- Send emails via SMTP
- Inbox / Sent / Trash
- Compose / Reply / Forward
- Outlook-style mailbox UI
    """,
    "category": "Tools",
    "author": "Cuong Odoo",
    "website": "https://hothanhcuong.site",
    "license": "LGPL-3",
    "depends": ["base", "mail", "web", "bus"],
    "data": [
        "security/mailbox_security.xml",
        "security/mailbox_rules.xml",
        "security/ir.model.access.csv",
        "data/mailbox_cron.xml",
        "views/mailbox_client_action.xml",
        "views/mailbox_account_views.xml",
        # "views/mailbox_folder_views.xml",
        # "views/mailbox_message_views.xml",
        # "views/mailbox_compose_wizard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "mailbox_client/static/src/js/mailbox_app.js",
            "mailbox_client/static/src/xml/mailbox_app.xml",
            "mailbox_client/static/src/scss/mailbox_app.scss",
        ],
    },
    "icon": "mailbox_client/static/src/Img/icon.png",
    "installable": True,
    "application": True,
}