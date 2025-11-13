# -*- coding: utf-8 -*-
from odoo import models, api


class ExecutiveDashboard(models.AbstractModel):
    _name = "wt.executive.dashboard"
    _description = "Executive Dashboard Data"

    @api.model
    def get_dashboard_data(self, filters=None):
        """Dashboard Giám đốc: Báo giá, đơn hàng, top sản phẩm & khách hàng"""
        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]

        # ===== 1️⃣ Lấy tham số lọc an toàn =====
        filters = filters or {}
        date_from = filters.get("date_from") or None
        date_to = filters.get("date_to") or None
        year_val = filters.get("year")
        year = int(year_val) if year_val and str(year_val).isdigit() else None
        quarter = filters.get("quarter") or None

        # ===== 2️⃣ Tính khoảng thời gian =====
        domain = []
        if quarter and year:
            quarters = {
                "Q1": ("01-01", "03-31"),
                "Q2": ("04-01", "06-30"),
                "Q3": ("07-01", "09-30"),
                "Q4": ("10-01", "12-31"),
            }
            start, end = quarters[quarter]
            date_from = f"{year}-{start}"
            date_to = f"{year}-{end}"
        elif year and not (date_from and date_to):
            date_from = f"{year}-01-01"
            date_to = f"{year}-12-31"

        # ===== 3️⃣ Áp dụng domain chung =====
        if date_from:
            domain.append(("create_date", ">=", date_from))
        if date_to:
            domain.append(("create_date", "<=", date_to))

        # ===== 4️⃣ KPI: Báo giá / Đơn hàng =====
        quotation_domain = domain + [("state", "in", ["draft", "sent"])]
        order_domain = domain + [("state", "in", ["sale", "done"])]

        quotation_count = SaleOrder.search_count(quotation_domain)
        order_count = SaleOrder.search_count(order_domain)
        conversion_rate = round((order_count / quotation_count) * 100, 2) if quotation_count else 0

        # ===== 5️⃣ Top sản phẩm =====
        line_domain = []
        if date_from:
            line_domain.append(("order_id.create_date", ">=", date_from))
        if date_to:
            line_domain.append(("order_id.create_date", "<=", date_to))

        product_stats = SaleOrderLine.read_group(
            line_domain + [("order_id.state", "in", ["draft", "sent", "sale", "done"])],
            fields=["product_id", "product_uom_qty:sum"],
            groupby=["product_id"],
            orderby="product_uom_qty:sum desc",
            limit=5,
        )

# --- 2️⃣ Gom riêng số lượng báo giá
        quotation_stats = SaleOrderLine.read_group(
            [("order_id.state", "in", ["draft", "sent"])],
            ["product_id", "product_uom_qty:sum"],
            ["product_id"]
        )
        quotation_map = {
            rec["product_id"][0]: rec["product_uom_qty"] for rec in quotation_stats if rec.get("product_id")
        }

# --- 3️⃣ Gom riêng số lượng đơn hàng đã bán
        order_stats = SaleOrderLine.read_group(
            [("order_id.state", "in", ["sale", "done"])],
            ["product_id", "product_uom_qty:sum"],
            ["product_id"]
        )
        order_map = {
            rec["product_id"][0]: rec["product_uom_qty"] for rec in order_stats if rec.get("product_id")
        }

        # --- 4️⃣ Tạo danh sách top_products
        top_products = []
        for rec in product_stats:
            product_id = rec.get("product_id")
            if not product_id:
                continue

            pid = product_id[0]
            product = self.env["product.product"].browse(pid)

            top_products.append({
                "name": product.display_name,
                "quotation_qty": round(quotation_map.get(pid, 0), 2),
                "order_qty": round(order_map.get(pid, 0), 2),
                "total_qty": round(rec.get("product_uom_qty", 0), 2),
            })

        # ===== 6️⃣ Top khách hàng =====
        customer_stats = SaleOrder.read_group(
            order_domain,
            fields=["partner_id", "amount_total:sum"],
            groupby=["partner_id"],
            orderby="amount_total:sum desc",
            lazy=False,
            limit=5,
        )

        top_customers = []
        for rec in customer_stats:
            partner_id = rec.get("partner_id")
            if partner_id:
                partner = self.env["res.partner"].browse(partner_id[0])
                order_count = rec.get("__count") or rec.get("partner_id_count") or 0  # fallback
                total_value = rec.get("amount_total") or 0.0
                top_customers.append({
                    "name": partner.display_name,
                    "order_count": int(order_count),
                    "total_value": round(total_value, 2),
                })

        # ===== 7️⃣ Trả dữ liệu =====
        return {
            "kpis": {
                "quotations": quotation_count,
                "orders": order_count,
                "conversion_rate": conversion_rate,
            },
            "top_products": top_products,
            "top_customers": top_customers,
            "date_from": date_from,
            "date_to": date_to,
            "year": year,
            "quarter": quarter,
        }
