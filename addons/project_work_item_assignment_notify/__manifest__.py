# -*- coding: utf-8 -*-
{
    "name": "Project Work Item Assignment Notification",
    "version": "17.0.1.0.0",
    "summary": "Thông báo khi phân công người phụ trách hạng mục công việc",
    "description": """
Thông báo realtime + chatter + activity khi phân công:
- Người báo cáo sản lượng
- Người báo cáo quyết toán
- Người báo cáo nghiệm thu
trên model project.work.item
    """,
    "category": "Project",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "project",
        "project_work_from_so",  # module của bạn có project.work.assignment / project.work.progress / project.work.item
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
        "assets": {
        "web.assets_backend": [
            "project_work_item_assignment_notify/static/src/js/assignment_notification_handler.js",
        ],
    },
    "installable": True,
    "application": False,
}