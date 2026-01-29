# -*- coding: utf-8 -*-
{
    'name': 'Company Loan Tracker',
    'version': '1.0',
    'summary': 'Quản lý và theo dõi các khoản vay của công ty',
    'category': 'Accounting/Finance',
    'author': 'SOMED',
    'depends': ['base', 'contacts', 'custom_account_menu','mail','custom_account_payment_request','custom_accounting_receipt','customer_account_payment_proposal','employee_advance_tracking','customer_debt'],
    'data': [
        'security/ir.model.access.csv',
        'views/company_loan_views.xml',
        'views/res_partner_view.xml',
        'views/account_payment_request.xml',
        'views/account_receipt.xml',
        'reports/report_company_loan.xml',
        'reports/report_company_loan_detail_templates.xml',
        'wizard/loan_detail_wizard_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
