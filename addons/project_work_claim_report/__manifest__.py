# -*- coding: utf-8 -*-
{
    "name": "Project Work Claim/Settlement Report",
    "summary": "Báo cáo thanh/quyết toán theo kỳ dựa trên báo cáo sản lượng",
    "version": "17.0.1.0.0",
    "category": "Project",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": [
        "project",
        "mail",
        "project_work_from_so",  # module hiện tại của bạn (có project.work.assignment / project.work.progress)
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_work_assignment_claim_config_views.xml",
        "views/project_work_assignment_claim_report_views.xml",
        # "views/project_project_work_item_claim_columns_inherit.xml",
        "views/project_project_assignment_claim_user_inherit.xml",
        "views/project_project_claim_report_button_inherit.xml",
    ],
    "installable": True,
    "application": False,
}