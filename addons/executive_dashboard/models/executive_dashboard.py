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
            lazy=False,
        )

        # 2️⃣ Lấy danh sách product_id có trong thống kê
        product_ids = [
            rec["product_id"][0]
            for rec in product_stats
            if rec.get("product_id")
        ]

        # 3️⃣ Đếm tổng số đơn (báo giá + đơn hàng) và gom order_ids theo product
        product_orders_map = {}

        if product_ids:
            # group theo (product_id, order_id) => 1 record = 1 đơn có sản phẩm đó
            order_groups = SaleOrderLine.read_group(
                product_line_domain + [("product_id", "in", product_ids)],
                fields=["order_id"],
                groupby=["product_id", "order_id"],
                lazy=False,
            )
            for g in order_groups:
                pid = g["product_id"][0]
                oid = g["order_id"][0]
                product_orders_map.setdefault(pid, set()).add(oid)

        # 4️⃣ Build top_products: doc_count = len(order_ids)
        top_products = []
        for rec in product_stats:
            product_id = rec.get("product_id")
            if not product_id:
                continue

            pid = product_id[0]
            product = self.env["product.product"].browse(pid)

            order_ids = list(product_orders_map.get(pid, set()))

            top_products.append({
                "name": product.display_name,
                # số đơn (báo giá + đơn hàng) có product này
                "doc_count": len(order_ids),
                # các đơn liên quan (sale.order)
                "order_ids": order_ids,
                # thêm thông tin SL + giá trị
                "total_qty": rec.get("product_uom_qty", 0.0),
                "total_amount": rec.get("price_subtotal", 0.0),
            })

        # 5️⃣ Sắp xếp theo tần suất xuất hiện rồi đến tổng giá trị
        TOP_N = 10  # tùy bạn muốn top mấy
        top_products.sort(key=lambda p: (-p["doc_count"], -p["total_amount"]))
        top_products = top_products[:TOP_N]

        

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

        # --- Đơn hàng theo khách hàng (kèm order_ids)
        order_customer_stats = SaleOrder.read_group(
            order_domain,
            fields=["partner_id", "amount_total:sum"],
            groupby=["partner_id"],
            lazy=False,
        )

        # Map partner -> tổng số + giá trị
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

        # 🔁 Gom danh sách order_ids theo partner để dùng cho chart click
        customer_orders_map = {}
        order_list = SaleOrder.search_read(order_domain, ["id", "partner_id"])
        for rec in order_list:
            partner = rec.get("partner_id")
            if not partner:
                continue
            pid = partner[0]
            customer_orders_map.setdefault(pid, []).append(rec["id"])

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
                # các đơn liên quan (sale.order)
                "order_ids": customer_orders_map.get(pid, []),
            })

        # sort & limit như cũ
        top_customers.sort(key=lambda c: (c["total_docs"], c["total_amount"]), reverse=True)
        top_customers = top_customers[:5]

        # ===== 7️⃣ Chi phí dự án (giữ nguyên logic cũ, thêm project_id để sau này cần click) =====
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
                "project_id": rec.project_id.id or False,
            })

        # ===== 8️⃣ Thu / chi tiền mặt / ngân hàng =====
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

        # ===== 9️⃣ Hóa đơn vào / ra =====
        SupplierInvoice = self.env["supplier.invoice"]
        supplier_invoices = SupplierInvoice.search_read(
            [
                ("date", ">=", date_from),
                ("date", "<=", date_to),
            ],
            ["id", "invoice_number", "name", "partner_id", "amount", "date", "due_date"],
            order="date desc",
        )
        total_supplier_invoice = sum(inv.get("amount") or 0.0 for inv in supplier_invoices)

        CustomerInvoice = self.env["customer.invoice"]
        customer_invoices = CustomerInvoice.search_read(
            [
                ("date", ">=", date_from),
                ("date", "<=", date_to),
            ],
            ["id", "name", "invoice_number", "partner_id", "amount_total", "date"],
            order="date desc",
        )
        total_customer_invoice = sum(inv.get("amount_total") or 0.0 for inv in customer_invoices)
        supplier_invoice_count = len(supplier_invoices)
        customer_invoice_count = len(customer_invoices)

        invoice_overview = {
            "supplier_total": total_supplier_invoice,
            "customer_total": total_customer_invoice,
            "supplier_count": supplier_invoice_count,
            "customer_count": customer_invoice_count,
        }

        # ===== 🔟 Trả dữ liệu =====
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
            "invoice_overview": invoice_overview,
            "top_products": top_products,        # thêm order_ids
            "top_customers": top_customers,      # thêm order_ids
            "project_expense": project_expense,
            "top_order": top_order_info,
            "conversion_rate": conversion_rate,
            # giữ nguyên các filter để FE hiển thị lại
            "date_from": date_from,
            "date_to": date_to,
            "year": year,
            "quarter": quarter,
        }
