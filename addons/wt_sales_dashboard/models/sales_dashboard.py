# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, timedelta

class SalesDashboard(models.AbstractModel):
    _name = 'wt.sales.dashboard'
    _description = 'Sales & Inventory Dashboard Model'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        now = datetime.now()
        # Chuẩn hoá date_to (end-of-day)
        if date_to:
            try:
                dt_to = datetime.fromisoformat(str(date_to)[:19])
            except Exception:
                dt_to = now
        else:
            dt_to = now
        dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)

        # Chuẩn hoá date_from
        if date_from:
            try:
                dt_from = datetime.fromisoformat(str(date_from)[:19])
            except Exception:
                dt_from = dt_to - timedelta(days=30)
        else:
            dt_from = dt_to - timedelta(days=30)
        dt_from = dt_from.replace(hour=0, minute=0, second=0, microsecond=0)

        # KPI
        sales_orders = self.env['sale.order'].search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ['sale', 'done']),
        ])
        total_sales = sum(sales_orders.mapped('amount_total'))
        order_count = len(sales_orders)
        avg_order_value = total_sales / order_count if order_count else 0.0

        low_stock_products = self.env['product.product'].search_count([
            ('type', 'in', ['product', 'consu']),
            ('qty_available', '<=', 10),
        ])

        # Sales by day (theo khoảng)
        days = (dt_to.date() - dt_from.date()).days + 1
        sales_by_day = {(dt_from + timedelta(days=i)).strftime('%Y-%m-%d'): 0 for i in range(days)}
        for o in sales_orders:
            key = o.date_order.strftime('%Y-%m-%d')
            if key in sales_by_day:
                sales_by_day[key] += o.amount_total
        sales_trend_labels = sorted(sales_by_day.keys())
        sales_trend_data = [sales_by_day[k] for k in sales_trend_labels]

        # Top products (theo khoảng)
        top_products_query = """
            SELECT sol.product_id, SUM(sol.product_uom_qty) AS total_qty
            FROM sale_order_line sol
            JOIN sale_order so ON sol.order_id = so.id
            WHERE so.date_order >= %s
              AND so.date_order <= %s
              AND so.state IN ('sale','done')
              AND sol.product_id IS NOT NULL
            GROUP BY sol.product_id
            ORDER BY total_qty DESC
            LIMIT 5
        """
        self.env.cr.execute(top_products_query, (dt_from, dt_to))
        tp_rows = self.env.cr.dictfetchall()
        pids = [r['product_id'] for r in tp_rows]
        products = self.env['product.product'].browse(pids)
        name_map = {p.id: p.display_name for p in products}
        uom_map  = {p.id: p.uom_id.display_name for p in products}

        top_products_labels = [name_map.get(r['product_id'], 'Unknown') for r in tp_rows]
        top_products_values = [r['total_qty'] for r in tp_rows]
        top_products_uoms   = [uom_map.get(r['product_id'], '') for r in tp_rows]

        # Recent orders (theo khoảng)
        recent_orders = self.env['sale.order'].search([
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ['sale', 'done']),
        ], order='date_order desc', limit=5)
        recent_orders_data = [{
            'id': o.id,
            'name': o.name,
            'partner': o.partner_id.name,
            'date': o.date_order.strftime('%Y-%m-%d'),
            'total': o.amount_total,
            'state': dict(o._fields['state'].selection).get(o.state),
        } for o in recent_orders]

        return {
            'kpis': {
                'total_sales': total_sales,
                'avg_order_value': avg_order_value,
                'order_count': order_count,
                'low_stock_products': low_stock_products,
            },
            'charts': {
                'sales_trend': {'labels': sales_trend_labels, 'data': sales_trend_data},
                'top_products': {'labels': top_products_labels, 'data': top_products_values, 'uoms': top_products_uoms},
            },
            'recent_orders': recent_orders_data,
        }
