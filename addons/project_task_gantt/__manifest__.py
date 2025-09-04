{
    'name': "Project Task Gantt",
    'version': '1.0',
    'summary': "Gantt chart view for project tasks",
    'depends': ['project', 'base', 'web'],
    'data': [
        'views/project_task_gantt.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'https://cdn.dhtmlx.com/gantt/edge/dhtmlxgantt.js',
            'https://cdn.dhtmlx.com/gantt/edge/dhtmlxgantt.css',
            'project_task_gantt/static/src/js/gantt_renderer.js',
            'project_task_gantt/static/src/xml/gantt_templates.xml',
            'project_task_gantt/static/src/css/gantt.css',
        ],
    },
    'application': False,
}
