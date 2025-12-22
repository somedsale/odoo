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
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "data/future_project_stage_data.xml",  # 👈 BẮT BUỘC

        "views/future_project_kanban.xml",
        "views/future_project_views.xml",
        "views/menu.xml",
    ],
    "application": True,
    "installable": True,
}
