{
    'name': 'Project Cost Custom',
    'version': '1.0',
    'summary': 'Quản lý chi phí thực tế của dự án',
    'description': 'Module giúp quản lý chi phí thực tế của dự án trong Odoo Community.',
    'author': 'ChatGPT + Bạn',
    'category': 'Project',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_cost_views.xml',
    ],
    'installable': True,
    'application': True,
}
