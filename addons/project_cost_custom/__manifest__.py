{
    'name': 'Project Cost Management',
    'version': '1.0',
    'summary': 'Quản lý chi phí dự án từ task',
    'category': 'Project',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_cost_views.xml',
    ],
    'installable': True,
    'application': False,
}
