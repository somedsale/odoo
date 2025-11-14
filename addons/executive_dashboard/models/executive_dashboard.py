# -*- coding: utf-8 -*-
from odoo import models, api


class ExecutiveDashboard(models.AbstractModel):
    _name = "wt.executive.dashboard"
    _description = "Executive Dashboard Data"

    @api.model
    def get_dashboard_data(self, filters=None):
        """Dashboard Giám đốc: Sale KPIs, top sản phẩm, top khách hàng, chi phí dự án."""
        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]

        # ===== 1️⃣ Lấy tham số lọc an toàn =====
        filters = filters or {}
        date_from = filters.get("date_from") or None
        date_to = filters.get("date_to") or None

        year_val = filters.get("year")
        year = int(year_val) if year_val and str(year_val).isdigit() else None
        quarter = filters.get("quarter") or None

        # ===== 2️⃣ Tính khoảng thời gian theo year/quarter (nếu có) =====
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

        # Áp dụng domain ngày chung cho sale.order
        if date_from:
            domain.append(("create_date", ">=", date_from))
        if date_to:
            domain.append(("create_date", "<=", date_to))

        # ===== 3️⃣ KPI: Báo giá / Đơn hàng (số lượng & tổng tiền) =====
        quotation_domain = domain + [("state", "in", ["draft", "sent"])]
        order_domain = domain + [("state", "in", ["sale", "done"])]

        # -- Báo giá
        quotation_count = SaleOrder.search_count(quotation_domain)
        quotation_group = SaleOrder.read_group(
            quotation_domain,
            fields=["amount_total:sum"],
            groupby=[],
        )
        quotation_total_amount = quotation_group[0]["amount_total"] if quotation_group else 0.0

        # -- Đơn hàng
        order_count = SaleOrder.search_count(order_domain)
        order_group = SaleOrder.read_group(
            order_domain,
            fields=["amount_total:sum"],
            groupby=[],
        )
        order_total_amount = order_group[0]["amount_total"] if order_group else 0.0

        conversion_rate = round((order_count / quotation_count) * 100, 2) if quotation_count else 0.0

        # ===== 4️⃣ Đơn hàng có giá trị cao nhất (hạng mục cao nhất) =====
        top_order_info = {}
        top_order = SaleOrder.search(order_domain, order="amount_total desc", limit=1)
        if top_order:
            top_order_info = {
                "name": top_order.name,
                "partner": top_order.partner_id.display_name,
                "amount_total": top_order.amount_total,
            }

        # ===== 5️⃣ Sản phẩm được chọn nhiều nhất (báo giá + đơn hàng) =====
        line_domain = []
        if date_from:
            line_domain.append(("order_id.create_date", ">=", date_from))
        if date_to:
            line_domain.append(("order_id.create_date", "<=", date_to))

        # Lấy thống kê theo product trên tất cả SO (draft, sent, sale, done)
        product_line_domain = line_domain + [
            ("order_id.state", "in", ["draft", "sent", "sale", "done"])
        ]

        # 1️⃣ Thống kê số lượng & giá trị để hiển thị
        product_stats = SaleOrderLine.read_group(
            product_line_domain,
            fields=["product_id", "product_uom_qty:sum", "price_subtotal:sum"],
            groupby=["product_id"],
            orderby="product_uom_qty:sum desc",
            limit=5,
        )

        # 2️⃣ Lấy danh sách product_id top 5
        product_ids = [
            rec["product_id"][0]
            for rec in product_stats
            if rec.get("product_id")
        ]

        # 3️⃣ Đếm tổng số đơn (báo giá + đơn hàng) có chứa từng sản phẩm
        order_count_map = {}
        if product_ids:
            # group theo (product_id, order_id) => mỗi dòng là 1 đơn có sản phẩm đó
            order_groups = SaleOrderLine.read_group(
                product_line_domain + [("product_id", "in", product_ids)],
                fields=["order_id"],
                groupby=["product_id", "order_id"],
                lazy=False,
            )
            for g in order_groups:
                pid = g["product_id"][0]
                order_count_map[pid] = order_count_map.get(pid, 0) + 1

        # 4️⃣ Build top_products: thêm field doc_count = tổng số đơn có sản phẩm đó
        top_products = []
        for rec in product_stats:
            product_id = rec.get("product_id")
            if not product_id:
                continue
            pid = product_id[0]
            product = self.env["product.product"].browse(pid)

            top_products.append({
                "name": product.display_name,
                # số đơn (báo giá + đơn hàng) có product này
                "doc_count": order_count_map.get(pid, 0),
                # nếu vẫn cần thì giữ lại 2 field cũ
                "total_qty": rec.get("product_uom_qty", 0.0),
                "total_amount": rec.get("price_subtotal", 0.0),
            })

        # Lấy sản phẩm top 1 (được chọn nhiều nhất)
        top_product_overall = {}
        if product_stats:
            best = product_stats[0]
            pid = best["product_id"][0]
            product = self.env["product.product"].browse(pid)
            top_product_overall = {
                "name": product.display_name,
                "total_qty": best.get("product_uom_qty", 0.0),
                "total_amount": best.get("price_subtotal", 0.0),
            }

        # ===== 6️⃣ Khách hàng có nhiều báo giá & đơn hàng =====
        # --- Báo giá theo khách hàng
        quotation_customer_stats = SaleOrder.read_group(
            quotation_domain,
            fields=["partner_id", "amount_total:sum"],
            groupby=["partner_id"],
            lazy=False,
        )

        quotation_map = {}
        for rec in quotation_customer_stats:
            partner = rec.get("partner_id")
            if not partner:
                continue
            pid = partner[0]
            quotation_map[pid] = {
                "quotation_count": rec.get("partner_id_count", rec.get("__count", 0)) or 0,
                "quotation_amount": rec.get("amount_total", 0.0) or 0.0,
            }

        # --- Đơn hàng theo khách hàng
        order_customer_stats = SaleOrder.read_group(
            order_domain,
            fields=["partner_id", "amount_total:sum"],
            groupby=["partner_id"],
            lazy=False,
        )

        customer_combined = {}
        for rec in order_customer_stats:
            partner = rec.get("partner_id")
            if not partner:
                continue
            pid = partner[0]
            customer_combined.setdefault(pid, {
                "quotation_count": 0,
                "quotation_amount": 0.0,
                "order_count": 0,
                "order_amount": 0.0,
            })
            customer_combined[pid]["order_count"] = rec.get("partner_id_count", rec.get("__count", 0)) or 0
            customer_combined[pid]["order_amount"] = rec.get("amount_total", 0.0) or 0.0

        # Gộp thêm phần báo giá
        for pid, qvals in quotation_map.items():
            customer_combined.setdefault(pid, {
                "quotation_count": 0,
                "quotation_amount": 0.0,
                "order_count": 0,
                "order_amount": 0.0,
            })
            customer_combined[pid]["quotation_count"] = qvals["quotation_count"]
            customer_combined[pid]["quotation_amount"] = qvals["quotation_amount"]

        # Build danh sách top khách hàng (sắp xếp theo tổng số chứng từ desc)
        top_customers = []
        for pid, vals in customer_combined.items():
            partner = self.env["res.partner"].browse(pid)
            total_docs = vals["quotation_count"] + vals["order_count"]
            total_amount = vals["quotation_amount"] + vals["order_amount"]

            # 🚫 Bỏ những khách hoàn toàn không có giá trị
            if not total_amount and not total_docs:
                continue

            top_customers.append({
                "name": partner.display_name,
                "quotation_count": int(vals["quotation_count"]),
                "order_count": int(vals["order_count"]),
                "quotation_amount": round(vals["quotation_amount"], 2),
                "order_amount": round(vals["order_amount"], 2),
                "total_docs": int(total_docs),
                "total_amount": round(total_amount, 2),
            })

        # sort & limit như cũ
        top_customers.sort(key=lambda c: (c["total_docs"], c["total_amount"]), reverse=True)
        top_customers = top_customers[:5]

        # ===== 7️⃣ Chi phí dự án (giữ nguyên logic cũ) =====
        Expense = self.env["project.expense.custom"]
        expense_records = Expense.search([
            ("total_spent", ">", 0),
            ("total_cost", ">", 0),
        ], limit=5, order="total_cost desc")

        project_expense = []
        for rec in expense_records:
            project_expense.append({
                "name": rec.name or (rec.project_id.name or "Không tên"),
                "spent": rec.total_spent or 0.0,
                "not_spent": rec.total_not_spent or 0.0,
                "total": rec.total_cost or 0.0,
            })
        Receipt = self.env["account.receipt"]
        PayReq = self.env["account.payment.request"]

        cash_in_domain = [("state", "in", ["posted"])]
        cash_out_domain = [("status_expense", "in", ["paid"])]

        if date_from:
            cash_in_domain.append(("date", ">=", date_from))
            cash_out_domain.append(("date_payment", ">=", date_from))
        if date_to:
            cash_in_domain.append(("date", "<=", date_to))
            cash_out_domain.append(("date_payment", "<=", date_to))

        cash_in = sum(
            r.get("amount") or 0.0
            for r in Receipt.search_read(cash_in_domain, ["amount"])
        )
        cash_out = sum(
            r.get("total") or 0.0
            for r in PayReq.search_read(cash_out_domain, ["total"])
        )

        # ===== 8️⃣ Trả dữ liệu =====
        return {
            "kpis": {
                "quotation": {
                    "count": quotation_count,
                    "total_amount": quotation_total_amount,
                },
                "order": {
                    "count": order_count,
                    "total_amount": order_total_amount,
                },
                "cash_in": cash_in,
                "cash_out": cash_out,
            },
            "top_products": top_products,        # vẫn usable cho chart nếu cần
            "top_customers": top_customers,      # đã gộp báo giá + đơn hàng
            "project_expense": project_expense,
            # giữ nguyên các filter để FE hiển thị lại
            "date_from": date_from,
            "date_to": date_to,
            "year": year,
            "quarter": quarter,
        }
