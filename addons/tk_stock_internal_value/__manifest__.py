# -*- coding: utf-8 -*-
{
    "name": "TK Stock Internal Value",
    "version": "17.0.1.0.0",
    "summary": "Thêm đơn giá & giá trị nội bộ trên phiếu kho",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": [
        "stock",
        "purchase_stock",  # để có purchase_line_id trên stock.move (nếu ông muốn auto lấy giá PO)
    ],
    "data": [
        "views/stock_picking_internal_value_views.xml",
        "views/stock_picking_tree_inherit.xml",
    ],
    "installable": True,
    "application": False,
}
