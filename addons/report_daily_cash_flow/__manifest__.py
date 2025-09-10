{
    'name': 'Daily Cash Flow Report',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Generate daily cash flow report for a single day based on payment requests and receipts',
    'depends': ['account', 'project', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/daily_cash_flow_wizard_view.xml',
        'reports/daily_cash_flow_report.xml',
    ],
    'installable': True,
    'auto_install': False,
}