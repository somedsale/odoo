{
    'name': 'Dashboard Chi Phí Dự Án',
    'version': '1.0',
    'depends': ['base', 'project', 'mail','cost_estimate'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_dashboard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_expense_dashboard/static/src/css/label_readonly.css',
        ],
    },
    'installable': True,
    'application': True,
}
