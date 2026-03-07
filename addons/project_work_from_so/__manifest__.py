{
    "name": "Project Work Items From Sale Order",
    "version": "17.0.1.0.0",
    "depends": [
        "project",
        "sale",
        "contract_management",
        "custom_sale_project",
        "proposal_sheet",
        "cost_estimate",
        "custom_project_expense",
        "web"
        # "your_contract_module_name",  # <- đổi thành tên module chứa model contract.management của bạn
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/project_work_rules.xml",
        "security/rules.xml",
        # "views/manager_work_item_dashboard_action.xml",
        "views/project_work_dashboard_action.xml",
        "views/project_project_custom_views.xml",
        "views/my_weekly_report_assignment_views.xml",
        "views/manager_work_item_views.xml",
        'views/project_rename_menu.xml',
        'views/project_work_item_views.xml',
    ],
        "assets": {
        "web.assets_backend": [
            "project_work_from_so/static/src/work_item_dashboard/work_item_dashboard.xml",
            "project_work_from_so/static/src/work_item_dashboard/work_item_dashboard.js",
            "project_work_from_so/static/src/work_item_dashboard/work_item_dashboard.scss",
            "project_work_from_so/static/src/project_dashboard/project_dashboard.xml",
            "project_work_from_so/static/src/project_dashboard/project_dashboard.js",
            "project_work_from_so/static/src/project_dashboard/project_dashboard.scss",
            'project_work_from_so/static/src/form/project_work_project_form_owl.js',
            'project_work_from_so/static/src/form/project_work_project_form_owl.xml',
            'project_work_from_so/static/src/form/project_work_project_form_owl.scss',

        ],
    },
    "installable": True,
    "application": False,
}
