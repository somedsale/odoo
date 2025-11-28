# -*- coding: utf-8 -*-
{
    "name": "Product Bundle Kit",
    "version": "17.0.1.0.0",
    "summary": "Sản phẩm cha - sản phẩm con để bán hàng & sản xuất",
    "author": "Somed",
    "website": "",
    "category": "Product",
    "depends": [
        "sale",
        "product",
        "mrp",
    ],
    "data": [
            "security/ir.model.access.csv",

        "views/product_bundle_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
}
