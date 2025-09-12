{
    'name': 'Custom Excel Export',
    'version': '1.0',
    'depends': ['base', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/export_excel_view.xml',
    ],
    'installable': True,
    'application': False,
}