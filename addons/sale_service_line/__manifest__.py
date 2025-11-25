# -*- coding: utf-8 -*-
{
    "name": "Sale Service Line",
    "version": "17.0.1.0.0",
    "summary": "Thêm trường dịch vụ cho dòng đơn bán hàng",
    "description": """
Thêm field 'service_name' vào sale.order.line để mô tả dịch vụ,
và tự động hiển thị 'Cung cấp & lắp đặt + tên sản phẩm' (hoặc nội dung dịch vụ khác).
""",
    "author": "Somed / Custom",
    "website": "",
    "license": "LGPL-3",
    "category": "Sales",
    "depends": ["sale"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
}
