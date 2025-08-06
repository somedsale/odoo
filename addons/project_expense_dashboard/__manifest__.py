{
    'name': 'Dashboard Chi Phí Dự Án',
    'version': '1.0',
    'depends': ['base', 'project', 'mail','cost_estimate'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_dashboard_views.xml',
    ],
    'installable': True,
    'application': True,
}
