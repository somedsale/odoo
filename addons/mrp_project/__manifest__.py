# -*- coding: utf-8 -*-
{
    "name": "MRP/Stock Project Link",
    "summary": "Thêm trường Dự án cho Lệnh sản xuất, dịch chuyển kho và phiếu kho",
    "version": "17.0.1.0.0",
    "author": "Somed/WT",
    "license": "LGPL-3",
    "depends": ["mrp", "stock", "project", "contract_management"],
    "data": [
        "security/ir.model.access.csv",
        "data/multi_mrp_order_sequence.xml",
        "views/mrp_production_views.xml",
        "views/multi_mrp_order_views.xml",
        # "views/stock_move_views.xml",
        "views/stock_picking_views.xml",
        "views/product_template_views.xml",
    ],
    "installable": True,
}
