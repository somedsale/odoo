{
    'name': 'Cost Estimate Accounting',
    'version': '1.0',
    'depends': ['cost_estimate','custom_account_menu'],
    'category': 'Accounting',
    'summary': 'Kế toán xem dự toán chi phí từ dự án',
    'data': [
        'security/ir.model.access.csv',
        'views/cost_estimate_accounting_views.xml',
    ],
    'installable': True,
    'application': False,
}
