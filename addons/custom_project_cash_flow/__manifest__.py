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
    'depends': ['base', 'account', 'project','custom_accounting_receipt'],
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'views/project_cash_flow_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'custom_project_cash_flow/static/src/xml/custom_list_render_cash_flow.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
