{
    'name': 'Quản Lý Công Nợ Nhà Cung Cấp',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Module quản lý công nợ với suppliers, projects, contracts, invoices',
    'description': 'Hiển thị danh sách nhà cung cấp với projects, contracts, settlement, invoices và công nợ.',
    'depends': ['account', 'project', 'purchase'],
    'data': [
        'security/ir.model.access.csv',
        'views/supplier_debt_views.xml',
    ],
    'installable': True,
    'application': True,
}