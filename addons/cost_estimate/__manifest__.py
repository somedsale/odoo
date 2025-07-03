{
    'name': 'Project Cost Estimate',
    'version': '1.0',
    'summary': 'Dự toán chi phí dự án',
    'category': 'Project',
    'depends': ['project', 'project_material', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/cost_estimate_views.xml',
    ],
    'installable': True,
    'application': False,
}
