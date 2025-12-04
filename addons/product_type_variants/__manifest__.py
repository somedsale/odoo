# -*- coding: utf-8 -*-
{
    "name": "Somed Product Types & Attribute Sets",
    "summary": "Loại sản phẩm + bộ thuộc tính riêng cho từng loại (biến thể thông minh)",
    "version": "17.0.1.0.0",
    "author": "Somed",
    "license": "LGPL-3",
    "website": "https://somed.vn",
    "category": "Product",
    "depends": ["product"],
    "data": [
        "security/ir.model.access.csv",
        "views/product_attribute_set_views.xml",
        "views/product_type_views.xml",
        "views/product_template_views.xml",
        "views/product_normal_form_view.xml",
    ],
    "installable": True,
    "application": False,
}
