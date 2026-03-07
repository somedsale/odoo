# -*- coding: utf-8 -*-
{
    "name": "Project Work Acceptance Report",
    "summary": "Báo cáo nghiệm thu theo kỳ cho hạng mục công việc",
    "version": "17.0.1.0.0",
    "category": "Project",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": [
        "project",
        "mail",
        "project_work_from_so",   # module của bạn có project.work.assignment / project.work.progress / project.work.item
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_work_assignment_acceptance_config_views.xml",
        "views/project_work_assignment_acceptance_report_views.xml",
        "views/project_project_acceptance_button_inherit.xml",
        "views/project_project_assignment_acceptance_user_inherit.xml",
        # "views/project_work_item_acceptance_inherit_views.xml",  # tuỳ chọn, nếu muốn hiện trên hạng mục
    ],
    "installable": True,
    "application": False,
}