# -*- coding: utf-8 -*-
{
    "name": "Project Work Acceptance Report",
    "version": "17.0.1.0.0",
    "summary": "Báo cáo nghiệm thu theo dự án",
    "category": "Project",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": [
        "web",
        "mail",
        "project",
        "sale_management",
        "project_work_from_so",
    ],
    "data": [
        "security/ir.model.access.csv",
        'wizard/project_acceptance_assign_multi_wizard_views.xml',
        "views/acceptance_views.xml",
        "views/acceptance_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "project_work_acceptance_report/static/src/js/acceptance_project_list.js",
            "project_work_acceptance_report/static/src/js/acceptance_report.js",
            "project_work_acceptance_report/static/src/xml/acceptance_report.xml",
            "project_work_acceptance_report/static/src/scss/acceptance_report.scss",
        ],
    },
    "installable": True,
    "application": False,
}