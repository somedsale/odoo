{
    'name': 'Project Cost Estimate',
    'version': '1.0',
    'summary': 'Dự toán chi phí dự án',
    'category': 'Project',
    'depends': ['project', 'sale', 'project_material'],
    'data': [
        'data/cost_estimate_sequence.xml',
        'security/ir.model.access.csv',
        'views/cost_estimate_views.xml',
    ],
    'installable': True,
    'application': False,
}
