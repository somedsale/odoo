{
    'name': 'Tổng hợp công nợ phải trả nhà cung cấp',
    'summary': 'Module tùy chỉnh để quản lý danh sách tổng hợp công nợ phải trả, với thông tin dự án, hợp đồng, v.v.',
    'description': '''
    Module này cho phép tạo danh sách tổng hợp công nợ phải trả cho nhà cung cấp,
    nhập thông tin: dự án, hợp đồng, hồ sơ quyết toán, hóa đơn, số tiền đã trả và số tiền còn nợ.
    ''',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'category': 'Accounting',
    'version': '1.0.0',
    'depends': ['base', 'account','custom_account_menu','contract_management', 'project'],  # Phụ thuộc vào module kế toán và dự án
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}