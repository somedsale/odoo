# -*- coding: utf-8 -*-
{
    'name': 'Project Expense Detail',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Chi tiết chi phí dự án theo đầu mục dự toán',
    'description': """
Quản lý chi tiết chi phí dự án:
- Gắn chi phí vào từng đầu mục của dự toán
- Phân loại chi phí: vật tư, nhân công, máy móc, dịch vụ
- Xem báo cáo group theo dự án và đầu mục
    """,
    'author': 'Your Name',
    'depends': ['project', 'product', 'uom','cost_estimate','custom_account_payment_request'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_expense_detail_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
