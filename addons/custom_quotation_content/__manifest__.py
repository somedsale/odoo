{
    "name": "Quotation Custom Info",
    "version": "1.0",
    "author": "Duy Dev",
    "category": "Sales",
    "summary": "Show Thông số và Xuất xứ in Quotation Line",
    "depends": ["sale", "product", "product_custom_info"],
    "data": [
        'security/ir.model.access.csv',
        "views/sale_order_views.xml",
        
    ],
    "installable": True,
    "application": False,
}
