{
    "name": "Account Payment Proposal",
    "version": "17.0.1.0.0",
    "summary": "Đề Nghị Giải Chi",
    "author": "Somed",
    "category": "Test",
    "depends": ["base","custom_account_payment_request","custom_accounting_receipt"],
    "data": [
        "security/account_payment_proposal_rules.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        "views/account_payment_proposal_view.xml",
        "views/account_payment_proposal_wizard_views.xml",
        'views/account_payment_proposal_reject_wizard_view.xml',
        "views/account_receipt_inherit.xml",
        ],
    "installable": True,
    "application": True,
}
