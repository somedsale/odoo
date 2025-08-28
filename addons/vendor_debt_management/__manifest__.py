{
    "name": "Supplier Debt Management",
    "version": "1.0",
    "author": "Your Company",
    "category": "Accounting",
    "depends": ["base", "project", "contacts", "custom_account_payment_request", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/supplier_contract_views.xml",
        "views/supplier_settlement_views.xml",
        "views/supplier_invoice_views.xml",
        "views/account_payment_request_views.xml",
        'views/supplier_views.xml',
        "report/report_supplier_summary.xml",
    ],
    "installable": True,
    "application": True,
}
