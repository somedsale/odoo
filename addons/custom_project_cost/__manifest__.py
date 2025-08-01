{
    'name': 'Project Cost Summary',
    'version': '1.0',
    'depends': ['project', 'account','custom_account_payment_request','custom_account_menu'],
    'author': 'Your Company',
    'category': 'Project',
    'description': 'Hiển thị tổng chi phí đã chi và chưa chi theo dự án',
    'data': [
        'security/ir.model.access.csv',
        'views/project_cost_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
