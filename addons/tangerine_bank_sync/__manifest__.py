# -*- coding: utf-8 -*-
{
    'name': 'Bank Information Vietnam',
    'summary': """Providing the latest API to synchronize banking information in Vietnam.""",
    'author': 'Long Duong Nhat',
    'website': 'https://github.com/long-dn',
    'category': 'Extra Tools',
    'support': 'odoo.tangerine@gmail.com',
    'version': '17.0.1.0',
    'depends': ['base'],
    'data': [
        'data/ir_cron.xml',
        'views/res_bank_views.xml'
    ],
    'images': ['static/description/thumbnail.png'],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}