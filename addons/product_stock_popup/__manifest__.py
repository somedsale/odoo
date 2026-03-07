# -*- coding: utf-8 -*-
{
    'name': 'Product Stock Info Popup',
    'version': '17.0.1.0.1',
    'category': 'Inventory/Inventory',
    'summary': 'Show product image and stock by location on hover',
    'description': """
        This module adds a hover popup on product fields in:
        - Sales Order Lines
        - Account Move Lines (Invoices)
        - Purchase Order Lines
        - Stock Move Lines

        The popup displays:
        - Product image
        - Stock quantities by location
        - Available and reserved quantities
    """,
    'author': 'Dato Zhuzhunadze',
    'depends': [
        'sale_management',
        'stock',
        'purchase',
        'account',
    ],
    'data': [],
    'images': ['static/description/banner.png'],
    'assets': {
        'web.assets_backend': [
            'product_stock_popup/static/src/js/product_stock_popover.js',
            'product_stock_popup/static/src/js/product_stock_field.js',
            'product_stock_popup/static/src/xml/product_stock_popover.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
