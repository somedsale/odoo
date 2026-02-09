{
    "name": "Project Work Items From Sale Order",
    "version": "17.0.1.0.0",
    "depends": [
        "project",
        "sale",
        "contract_management",
        "custom_sale_project"
        # "your_contract_module_name",  # <- đổi thành tên module chứa model contract.management của bạn
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/project_work_rules.xml",
        "security/rules.xml",
        "views/project_project_custom_views.xml",
        "views/my_weekly_report_assignment_views.xml",
        "views/manager_work_item_views.xml",
    ],
    "installable": True,
    "application": False,
}
