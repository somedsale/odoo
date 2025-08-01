{
    'name': 'Project Expense',
    'version': '1.0',
    'summary': 'Quản lý chi phí dự án',
    'description': 'Module quản lý chi phí dự án, hiển thị tổng chi phí, tổng đã chi và tổng chưa chi.',
    'category': 'Accounting',
    'depends': ['custom_account_payment_request', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_view.xml',
    ],
    'installable': True,
    'application': True,
}