{
    'name': 'Project Expense',
    'version': '1.0',
    'summary': 'Quản lý chi phí dự án',
    'description': 'Module quản lý chi phí dự án, hiển thị tổng chi phí, tổng đã chi và tổng chưa chi.',
    'category': 'Accounting',
    'depends': ['custom_account_payment_request', 'project','cost_estimate'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_view.xml',
        'views/account_payment_request_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_project_expense/static/src/scss/style.scss',
            "custom_project_expense/static/src/project_expense_owl/project_expense_list.js",
            "custom_project_expense/static/src/project_expense_owl/project_expense_list.xml",
            "custom_project_expense/static/src/project_expense_owl/project_expense_list.scss",
        ],
    },
    'installable': True,
    'application': True,
}