# custom_sale_order_type/__manifest__.py
{
    "name": "Sale Order Customer Type",
    "version": "17.0.1.0.0",
    "category": "Sales",
    "summary": "Phân loại báo giá theo khách online hoặc trực tiếp",
    "depends": ["sale"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}