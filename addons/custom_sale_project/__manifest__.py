{
    'name': 'Auto Create Project from Sale Order',
    'version': '1.0',
    'depends': ['sale', 'project', 'base'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_config_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}