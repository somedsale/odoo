/** @odoo-module **/

import { Component } from "@odoo/owl";

export class ProductStockPopover extends Component {
    static template = "product_stock_popup.ProductStockPopover";
    static props = {
        close: { type: Function, optional: true },
        stockInfo: { type: Object },
        formatMoney: { type: Function, optional: true },
    };
}
