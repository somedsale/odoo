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
    "assets": {
        "web.assets_backend": [
            "report_daily_cash_flow/static/src/js/daily_cash_flow_report.js",
            "report_daily_cash_flow/static/src/xml/daily_cash_flow_report.xml",
            "report_daily_cash_flow/static/src/scss/daily_cash_flow_report.scss",
        ],
    },
    'installable': True,
    'auto_install': False,
}