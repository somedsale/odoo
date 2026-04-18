{
    "name": "Hosting Contact Sync",
    "version": "17.0.1.0.0",
    "summary": "Đồng bộ contact từ hosting vào Odoo CRM",
    "description": """
Đồng bộ contact từ hosting vào Odoo
- Kéo contact từ hosting API
- Lưu vào model trung gian
- Tạo/cập nhật CRM Lead
- Có nút đồng bộ trên tree/form
- Có cron tự động
    """,
    "category": "CRM",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": ["base", "mail", "contacts", "sale_management"],
    "data": [
        "security/ir.model.access.csv",
        # "data/ir_cron.xml",
        "views/hosting_contact_views.xml",
        # "views/crm_lead_views.xml",
        "views/res_config_settings_views.xml",
    ],
    "icon": "/hosting_contact_sync/static/description/icon.png",
    "installable": True,
    "application": True,
}