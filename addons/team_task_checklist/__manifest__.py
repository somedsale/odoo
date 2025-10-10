{
    "name": "Company To-Do (Shared Tasks)",
    "version": "1.0",
    "summary": "Danh sách công việc / checklist dùng chung toàn công ty",
    "category": "Productivity",
    "depends": ["base",'hr'],
    "data": [
        "security/team_todo_security.xml",
        "security/ir.model.access.csv",
        "views/team_todo_view.xml",
    ],
    "application": True,  # Hiển thị ngoài menu chính
    "installable": True,
}
