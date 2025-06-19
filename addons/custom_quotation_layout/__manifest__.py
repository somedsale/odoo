{
    'name': 'Custom Quotation Layout',
    'version': '1.0',
    'summary': 'Customize quotation layout for Odoo',
    'depends': ['sale'],  # Module này phụ thuộc vào module sale
    'data': [
        'views/sale_order_views.xml',  # File XML chứa tùy chỉnh giao diện
    ],
    'css': [
    'static/css/custom_quotation.css',
    ],
    'installable': True,
    'auto_install': False,
}