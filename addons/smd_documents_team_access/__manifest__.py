{
    'name': 'SOMED Documents Management',
    'version': '1.0',
    'summary': 'Ứng dụng quản lý tài liệu theo Workspace và Team',
    'description': """
Ứng dụng độc lập quản lý tài liệu nội bộ:
- Workspace: thư mục chính
- Team: nhóm người dùng có quyền truy cập
- Document: file, liên kết hoặc ghi chú
- Phân quyền leader/member, quản lý theo workspace
    """,
    'author': 'SOMED',
    'category': 'Documents',
    'depends': ['base', 'mail'],
    'data': [
        'security/smd_documents_security.xml',
        'security/ir.model.access.csv',
        'views/menu.xml',
        'views/document_team_views.xml',
        'views/document_workspace_views.xml',
        'views/document_file_views.xml',
    ],
    'application': True,
    'installable': True,
}
