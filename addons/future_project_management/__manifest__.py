{
    "name": "Future Project Management",
    "version": "17.0.1.0.0",
    "category": "Project",
    "summary": "Manage potential / future projects before CRM or Project",
    "description": """
Manage future & potential projects:
- Early-stage project tracking
- Kanban pipeline
- Expected value & probability
- Convert to CRM / Project later
""",
    "author": "Somed",
    "depends": [
        "base",
        "mail",
        "crm",
        "project",
        "sale"
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/future_project_stage_data.xml",  # 👈 BẮT BUỘC
        "views/future_project_location_action.xml",
        "views/future_project_location_views.xml",
        "views/future_project_kanban.xml",
        "views/future_project_views.xml",
        "wizard/future_project_report_wizard_views.xml",
        "report/future_project_template.xml",
        "report/future_project_pdf_report.xml",
        "report/future_project_html_report.xml",
        "views/menu.xml",
        "views/future_project_report_dashboard_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "future_project_management/static/src/report_dashboard/dashboard.scss",
            "future_project_management/static/src/report_dashboard/dashboard.xml",
            "future_project_management/static/src/report_dashboard/dashboard.js",
        ],
    },
    "application": True,
    "installable": True,
}
