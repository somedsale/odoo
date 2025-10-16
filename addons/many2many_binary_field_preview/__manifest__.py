# -*- coding: utf-8 -*-
{
    'name': "Preview Attachments(Many2many)",
    'summary': "Preview Attachments(Image, GIF, Video, PDF, TXT)",
    'description': """This widget supports opening a popup to preview files on the current page.
    Supported file types: Image, GIF, Video, PDF, TXT.
    """,
    'author': "Lucas",
    'website': "",
    'category': 'Technical',
    'version': '1.0',
    'depends': ['base', 'web', 'mail'],
    'assets': {
        'web.assets_backend': [
            'many2many_binary_field_preview/static/src/many2many_binary_field_preview.xml',
            'many2many_binary_field_preview/static/src/many2many_binary_field_preview.js',
        ],
    },
    'images': [
        'static/description/home.png',
    ],
    'installable': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
