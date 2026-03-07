# -*- coding: utf-8 -*-
{
    "name": "Proposal Sheet Info Popup",
    "version": "17.0.1.0.0",
    "category": "Accounting",
    "summary": "Hover popup for Proposal Sheet (Phiếu Đề Xuất) many2one fields",
    "description": """
Show a modern hover popup when hovering a many2one field to proposal.sheet.

Target:
- account.payment.request / proposal_sheet_id

Popup shows:
- Proposal code, state
- Requested by, Project, Proposal type
- Totals
- Proposal lines in a table (material/expense/other)
""",
    "author": "Somed / ChatGPT",
    "depends": [
        "web",
        "mail",
        "project",
        "account",
        "hr",
        "proposal_sheet",
        "custom_account_payment_request",
        # IMPORTANT: add the module that defines model `proposal.sheet` here (your custom proposal module)
    ],
    "data": [],
    "assets": {
        "web.assets_backend": [
            "proposal_sheet_popup/static/src/js/proposal_sheet_popover.js",
            "proposal_sheet_popup/static/src/js/proposal_sheet_field.js",
            "proposal_sheet_popup/static/src/xml/proposal_sheet_popover.xml",
            "proposal_sheet_popup/static/src/scss/proposal_sheet_popover.scss",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
