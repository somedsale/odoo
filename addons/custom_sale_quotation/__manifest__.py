{
    'name': 'Custom Sale Quotation',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Customize Sale Quotation in Odoo',
    'description': """
        Module to customize the sale quotation form and functionalities.
    """,
    'depends': ['sale'],  # Phụ thuộc vào module sale
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}