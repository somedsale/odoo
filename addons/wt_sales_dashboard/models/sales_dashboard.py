# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import datetime, timedelta


class SalesDashboard(models.AbstractModel):
    _name = 'wt.sales.dashboard'
    _description = 'Sales & Inventory Dashboard Model'

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None, customer_type=None):
        now = datetime.now()

        # =========================
        # Chuẩn hoá date_to: end of day
        # =========================
        if date_to:
            try:
                dt_to = datetime.fromisoformat(str(date_to)[:19])
            except Exception:
                dt_to = now
        else:
            dt_to = now

        dt_to = dt_to.replace(hour=23, minute=59, second=59, microsecond=999999)

        # =========================
        # Chuẩn hoá date_from: start of day
        # =========================
        if date_from:
            try:
                dt_from = datetime.fromisoformat(str(date_from)[:19])
            except Exception:
                dt_from = dt_to - timedelta(days=30)
        else:
            dt_from = dt_to - timedelta(days=30)

        dt_from = dt_from.replace(hour=0, minute=0, second=0, microsecond=0)

        SaleOrder = self.env['sale.order'].sudo()

        # =========================
        # Domain dùng chung
        # =========================
        base_domain = [
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
        ]

        # customer_type: "" | False | online | direct
        # Chỉ lọc khi có chọn Online / Trực tiếp
        if customer_type:
            base_domain.append(('customer_type', '=', customer_type))

        # =========================
        # KPI: Đơn bán / Doanh thu
        # Chỉ tính đơn đã xác nhận
        # =========================
        sales_domain = base_domain + [
            ('state', 'in', ['sale', 'done']),
        ]

        sales_orders = SaleOrder.search(sales_domain)

        total_sales = sum(sales_orders.mapped('amount_total'))
        order_count = len(sales_orders)
        avg_order_value = (total_sales / order_count) if order_count else 0.0

        # =========================
        # KPI: Báo giá
        # Quan trọng:
        # Báo giá phải bao gồm cả các báo giá đã chuyển thành đơn bán/doanh thu.
        #
        # draft/sent = báo giá chưa xác nhận
        # sale/done = báo giá đã xác nhận, đã nằm trong doanh thu
        # =========================
        quotation_domain = base_domain + [
            ('state', 'in', ['draft', 'sent', 'sale', 'done']),
        ]

        quotation_orders = SaleOrder.search(quotation_domain)

        total_quotations = sum(quotation_orders.mapped('amount_total'))
        quotation_count = len(quotation_orders)

        # =========================
        # Tỉ lệ chuyển đổi
        # Theo giá trị: doanh thu / tổng báo giá
        # Theo số lượng: số đơn đã chốt / tổng số báo giá
        # =========================
        close_rate_value = (total_sales / total_quotations * 100) if total_quotations else 0.0
        close_rate_count = (order_count / quotation_count * 100) if quotation_count else 0.0

        # =========================
        # Contract - giữ logic cũ
        # Lưu ý: contract.management không có customer_type nên không lọc ở đây
        # =========================
        contract_orders = self.env['contract.management'].sudo().search([
            ('signature_date', '>=', dt_from),
            ('signature_date', '<=', dt_to),
        ])

        total_contract = sum(contract_orders.mapped('contract_value'))
        contract_count = len(contract_orders)

        # =========================
        # Hạng mục bán hàng
        # Tổng số category trong hệ thống, không phụ thuộc filter
        # =========================
        category_count = self.env['sale.order.category'].sudo().search_count([])

        # =========================
        # Chart: Sales by day
        # Chỉ lấy doanh thu từ sale/done
        # =========================
        days = (dt_to.date() - dt_from.date()).days + 1

        sales_by_day = {
            (dt_from + timedelta(days=i)).strftime('%Y-%m-%d'): 0
            for i in range(days)
        }

        for o in sales_orders:
            if not o.date_order:
                continue

            key = o.date_order.strftime('%Y-%m-%d')

            if key in sales_by_day:
                sales_by_day[key] += o.amount_total

        sales_trend_labels = sorted(sales_by_day.keys())
        sales_trend_data = [sales_by_day[k] for k in sales_trend_labels]

        # =========================
        # Chart: Top products
        # Chỉ lấy sản phẩm từ đơn đã chốt sale/done
        # Dùng SQL nên phải cộng thêm điều kiện customer_type thủ công
        # =========================
        top_products_where = """
            so.date_order >= %s
            AND so.date_order <= %s
            AND so.state IN ('sale', 'done')
            AND sol.product_id IS NOT NULL
        """
        top_products_params = [dt_from, dt_to]

        if customer_type:
            top_products_where += """
                AND so.customer_type = %s
            """
            top_products_params.append(customer_type)

        top_products_query = f"""
            SELECT sol.product_id, SUM(sol.product_uom_qty) AS total_qty
            FROM sale_order_line sol
            JOIN sale_order so ON sol.order_id = so.id
            WHERE {top_products_where}
            GROUP BY sol.product_id
            ORDER BY total_qty DESC
            LIMIT 5
        """

        self.env.cr.execute(top_products_query, tuple(top_products_params))
        tp_rows = self.env.cr.dictfetchall()

        pids = [r['product_id'] for r in tp_rows]
        products = self.env['product.product'].sudo().browse(pids)

        name_map = {p.id: p.display_name for p in products}
        uom_map = {p.id: p.uom_id.display_name for p in products}

        top_products_labels = [
            name_map.get(r['product_id'], 'Unknown')
            for r in tp_rows
        ]

        top_products_values = [
            r['total_qty']
            for r in tp_rows
        ]

        top_products_uoms = [
            uom_map.get(r['product_id'], '')
            for r in tp_rows
        ]

        top_products_ids = [
            r['product_id']
            for r in tp_rows
        ]

        # =========================
        # Chart: Hạng mục bán hàng
        # Tính theo số đơn trong khoảng ngày + customer_type
        # Bao gồm cả báo giá và đơn đã chốt
        # =========================
        all_orders_domain = base_domain + [
            ('state', 'in', ['draft', 'sent', 'sale', 'done']),
        ]

        all_orders = SaleOrder.search(all_orders_domain)

        category_counter = {}

        for so in all_orders:
            for cat in so.sales_category_ids:
                category_counter[cat.id] = category_counter.get(cat.id, 0) + 1

        sorted_items = sorted(
            category_counter.items(),
            key=lambda x: x[1],
            reverse=True
        )

        cat_ids_sorted = [cid for cid, _count in sorted_items]
        cats_browse = self.env['sale.order.category'].sudo().browse(cat_ids_sorted)

        cat_labels = [c.display_name for c in cats_browse]
        cat_counts = [category_counter.get(c.id, 0) for c in cats_browse]

        palette = [
            "#6366F1", "#3B82F6", "#06B6D4", "#10B981",
            "#84CC16", "#F59E0B", "#EF4444", "#8B5CF6",
            "#EC4899", "#22C55E", "#F97316", "#0EA5E9",
        ]

        cat_colors = []

        for idx, c in enumerate(cats_browse):
            if c.color is not None and 0 <= c.color < len(palette):
                cat_colors.append(palette[c.color])
            else:
                cat_colors.append(palette[idx % len(palette)])

        # =========================
        # Recent orders
        # Chỉ hiện đơn bán gần đây sale/done
        # =========================
        recent_orders_domain = base_domain + [
            ('state', 'in', ['sale', 'done']),
        ]

        recent_orders = SaleOrder.search(
            recent_orders_domain,
            order='date_order desc',
            limit=5
        )

        recent_orders_data = []

        state_selection = dict(SaleOrder._fields['state'].selection)

        customer_type_selection = {}

        if 'customer_type' in SaleOrder._fields:
            customer_type_selection = dict(SaleOrder._fields['customer_type'].selection)

        for o in recent_orders:
            cats = [
                {
                    'id': c.id,
                    'name': c.display_name,
                    'color': c.color or 0,
                }
                for c in o.sales_category_ids
            ]

            recent_orders_data.append({
                'id': o.id,
                'name': o.name,
                'partner': o.partner_id.name or '',
                'date': fields.Datetime.context_timestamp(self, o.date_order).strftime('%d/%m/%Y') if o.date_order else '',
                'total': o.amount_total,
                'state': state_selection.get(o.state, o.state),
                'categories': cats,

                # Trả thêm nếu sau này muốn hiện ở bảng recent orders
                'customer_type': o.customer_type or '',
                'customer_type_label': customer_type_selection.get(o.customer_type, ''),
            })

        return {
            'kpis': {
                'total_sales': total_sales,
                'avg_order_value': avg_order_value,
                'order_count': order_count,

                # Tổng báo giá đã bao gồm draft/sent/sale/done
                'total_quotations': total_quotations,
                'quotation_count': quotation_count,

                'close_rate_value': round(close_rate_value, 1),
                'close_rate_count': round(close_rate_count, 1),

                'category_count': category_count,

                # Giữ lại nếu sau này frontend cần dùng
                'total_contract': total_contract,
                'contract_count': contract_count,
            },
            'charts': {
                'sales_trend': {
                    'labels': sales_trend_labels,
                    'data': sales_trend_data,
                },
                'top_products': {
                    'labels': top_products_labels,
                    'data': top_products_values,
                    'uoms': top_products_uoms,
                    'ids': top_products_ids,
                },
                'sale_categories': {
                    'labels': cat_labels,
                    'data': cat_counts,
                    'colors': cat_colors,
                    'ids': cat_ids_sorted,
                },
            },
            'recent_orders': recent_orders_data,
        }