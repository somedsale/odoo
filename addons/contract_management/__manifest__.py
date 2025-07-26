{
    'name': 'Contract Management',
    'version': '1.0',
    'summary': 'Manage contracts linked to sale orders with stages and project creation',
    'description': """
        This module creates contracts from sale orders with stages: 
        Đang thương thảo hợp đồng, Chuẩn bị thực hiện, Đang thực hiện, Hoàn thành, 
        and creates a project when reaching the Đang thực hiện stage.
    """,
    'category': 'Sales',
    'author': 'Your Name',
    'depends': ['sale', 'project','hr', 'custom_department_manager'],  # Added custom_department_manager dependency
    'data': [
        'security/ir.model.access.csv',
        'views/contract_management_views.xml',
        'views/project_task_views.xml',

    ],
    'installable': True,
    'auto_install': False,
}