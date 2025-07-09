{
    'name': 'Project Material',
    'version': '17.0.1.0',
    'category': 'Project',
    'summary': 'Quản lý vật tư dự án',
    'author': 'Your Name',
    'depends': ['base', 'uom', 'product','project'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/material_views.xml',
        'views/material_views_line.xml',
        'views/material_category_views.xml',
    ],
    'installable': True,
    'application': True,
}
