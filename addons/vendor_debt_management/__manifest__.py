{
    "name": "Supplier Debt Management",
    "version": "1.0",
    "author": "Your Company",
    "category": "Accounting",
    "depends": ["base", "project", "contacts", "custom_account_payment_request", "web", "account"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/supplier_contract_views.xml",
        "views/supplier_settlement_views.xml",
        "views/supplier_invoice_views.xml",
        "views/account_payment_request_views.xml",
        'views/supplier_views.xml',
        "report/report_supplier_summary.xml",
        "report/report_supplier_detail.xml",
        "report/report_supplier_invoice.xml",
        "wizard/wizard_views.xml",
        "wizard/supplier_invoice_wizard.xml"
    ],
    "installable": True,
    "application": True,
}
