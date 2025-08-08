{
    'name': 'Project Cash Flow',
    'version': '1.0',
    'summary': 'Quản lý dòng tiền theo dự án',
    'description': '''
Module giúp quản lý các khoản thu/chi theo từng dự án,
bao gồm dòng tiền thực tế liên quan đến các đối tác và chứng từ.
''',
    'author': 'Your Company',
    'website': 'https://yourcompany.com',
    'category': 'Accounting/Project',
    'depends': ['base', 'account', 'project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_cash_flow_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
