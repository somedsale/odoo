# -*- coding: utf-8 -*-
{
    "name": "Project Disbursement Report",
    "summary": "Báo cáo giải ngân/thu tiền theo dự án từ hóa đơn khách hàng",
    "version": "17.0.1.0.0",
    "category": "Project",
    "author": "OpenAI",
    "license": "LGPL-3",
    "depends": [
        "base",
        "mail",
        "project",
        # module chứa customer.invoice / account.receipt của bạn:
        # thay bằng tên module thực tế
        "customer_debt",
        "project_work_from_so",  # module hiện tại của bạn (có project.project)
        "project_work_claim_report",  # để liên kết với báo cáo thanh toán
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/project_disbursement_report_views.xml",
        "views/project_project_inherit_views.xml",
        # "views/customer_invoice_project_summary_menu.xml",
        # "data/ir_cron.xml",
    ],
    "installable": True,
    "application": False,
}