{
    'name': 'Quản lý hợp đồng mua',
    'summary': 'Module tùy chỉnh để quản lý hợp đồng mua với nhà cung cấp.',
    'description': '''
    Module này cho phép tạo và quản lý hợp đồng mua, bao gồm thông tin số hợp đồng, nhà cung cấp, ngày ký, giá trị, điều khoản, v.v.
    ''',
    'author': 'Your Name',
    'website': 'https://yourwebsite.com',
    'category': 'Purchase',
    'version': '1.0.0',
    'depends': ['base', 'purchase', 'account', 'custom_account_menu', 'project'],  # Phụ thuộc vào mua hàng và kế toán
    'data': [
        'security/ir.model.access.csv',
        'views/views.xml',
        'views/menu.xml',
        'views/purchase_report_template.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}