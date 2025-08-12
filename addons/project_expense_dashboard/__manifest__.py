{
    'name': 'Dashboard Chi Phí Dự Án',
    'version': '1.0',
    'depends': ['base', 'project', 'mail','cost_estimate','custom_account_payment_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_dashboard_views.xml',
        'views/cost_estimate_line_view.xml',
        'views/account_payment_reqeust_inherit.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'project_expense_dashboard/static/src/css/label_readonly.css',
        ],
    },
    'installable': True,
    'application': True,
}
