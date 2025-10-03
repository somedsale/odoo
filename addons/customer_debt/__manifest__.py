# -*- coding: utf-8 -*-
{
    'name': "Customer Debt Management",
    'summary': "Quản lý công nợ khách hàng (Hợp đồng & Hóa đơn)",
    'description': """
Module quản lý công nợ khách hàng:
- Quản lý hợp đồng khách hàng
- Quản lý hóa đơn (có thể có hoặc không có hợp đồng)
- Tính toán công nợ theo hợp đồng
    """,
    'author': "Somed",
    'website': "https://somed.vn",
    'category': 'Accounting',
    'version': '1.0',
    'depends': ['base', 'mail'],
    'data': [
        # Security
        'security/ir.model.access.csv',
        'data/sequence.xml',
        # Views
        'views/contract_views.xml',
        'views/invoice_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
