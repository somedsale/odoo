{
    'name': 'Auto Create Project from Sale Order',
    'version': '1.0',
    'depends': ['sale', 'project', 'base'],
    'data': [
        'data/cron_data.xml',
        'security/ir.model.access.csv',
        'views/project_config_views.xml',
        'views/project_task_inherit_view.xml',
        'views/task_production_report_views.xml',
        'views/task_production_message_template.xml', 
        'views/project_project_view.xml',
    ],
    'installable': True,
    'auto_install': False,
}