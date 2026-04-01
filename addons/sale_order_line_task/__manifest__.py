# -*- coding: utf-8 -*-
{
    "name": "Sale Order Line -> Task (bulk)",
    "version": "17.0.1.0.0",
    "summary": "Create project tasks from sale.order.line in bulk",
    "description": "Wizard to generate project.task records from selected sale.order.line",
    "category": "Sales",
    "author": "Your Name",
    "depends": ["sale", "project","base",'web','contract_management'],
    "data": [
        "security/ir.model.access.csv",
        "views/wizard_create_tasks_views.xml",
        "views/add_button_to_project_form.xml",
        "views/add_button_assign_user_multitask.xml",
        "views/wizard_assign_user_task.xml",
        "views/hide_menu.xml",
        # "views/hide_item_in_task_project.xml",
    ],
    "installable": True,
    "application": False,
}