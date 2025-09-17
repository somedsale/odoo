{
    "name": "Proposal Sheet ↔ Purchase (per Vendor)",
    "version": "17.0.1.0.0",
    "summary": "Bổ sung vào proposal.sheet: tạo 1 RFQ/PO cho mỗi Nhà cung cấp từ dòng vật tư.",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": ["purchase", "project", "uom", "mail", "proposal_sheet", "custom_account_payment_request", "vendor_debt_management", "purchase_stock"],
    "data": [
        "security/ir.model.access.csv",
        "views/proposal_sheet_inherit_views.xml",
        "views/purchase_order_inherit_views.xml",
        "views/project_task_inherit_views.xml", 
        "views/purchase_advance_payment_wizard_views.xml",

    ],
    "installable": True,
    "application": False,
}
