# -*- coding: utf-8 -*-
{
    "name": "Project Work Finalization Report",
    "version": "17.0.1.0.0",
    "summary": "Báo cáo thanh/quyết toán theo dự án",
    "category": "Project",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": [
        "web",
        "mail",
        "project",
        "sale_management",
        "project_work_from_so",
        "project_work_acceptance_report",
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/project_finalization_assign_multi_wizard_views.xml",
        "views/finalization_views.xml",
        "views/finalization_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "project_work_finalization_report/static/src/js/finalization_project_list.js",
            "project_work_finalization_report/static/src/js/finalization_report.js",
            "project_work_finalization_report/static/src/xml/finalization_report.xml",
            "project_work_finalization_report/static/src/scss/finalization_report.scss",
        ],
    },
    "installable": True,
    "application": False,
}