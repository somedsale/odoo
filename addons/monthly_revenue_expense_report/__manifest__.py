# -*- coding: utf-8 -*-
{
    'name': "Monthly Revenue Expense Report",
    'summary': "Báo cáo Doanh thu - Chi phí hàng tháng (tổng hợp từ Phiếu Thu)",
    'version': '1.1',
    'depends': ['account', 'mail','custom_account_payment_request','custom_accounting_receipt'],
    'author': "Somed / ChatGPT",
    'category': 'Accounting',
    'license': 'LGPL-3',
'data': [
    'security/ir.model.access.csv',
    'views/report_revenue_expense_action.xml',
    'views/report_monthly_revenue_expense_template.xml',
    'views/account_payment_request.xml',
    'views/report_expense_bucket_views.xml',
    'data/migrate_expense_bucket_server_action.xml',
    'data/report_expense_bucket_data.xml',
],
"assets": {
    "web.assets_backend": [
        "monthly_revenue_expense_report/static/src/js/revenue_expense_report.js",
        "monthly_revenue_expense_report/static/src/xml/revenue_expense_report.xml",
        "monthly_revenue_expense_report/static/src/scss/revenue_expense_report.scss",
    ],
},
    'application': False,
    'installable': True,
}
