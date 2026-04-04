# -*- coding: utf-8 -*-
from odoo import models, api, fields


class ExecutiveDashboard(models.AbstractModel):
    _name = "wt.executive.dashboard"
    _description = "Executive Dashboard Data"

    @api.model
    def get_dashboard_data(self, filters=None):
        filters = filters or {}

        SaleOrder = self.env["sale.order"]
        SaleOrderLine = self.env["sale.order.line"]
        Expense = self.env["project.expense.custom"]
        Receipt = self.env["account.receipt"]
        PayReq = self.env["account.payment.request"]
        SupplierInvoice = self.env["supplier.invoice"]
        CustomerInvoice = self.env["customer.invoice"]
        Project = self.env["project.project"]
        ProposalSheet = self.env["proposal.sheet"]
        PaymentProposal = self.env["account.payment.proposal"]

        # =========================
        # 1. Resolve filter dates
        # =========================
        date_from = filters.get("date_from") or None
        date_to = filters.get("date_to") or None

        year_val = filters.get("year")
        year = int(year_val) if year_val and str(year_val).isdigit() else None
        quarter = filters.get("quarter") or None

        if quarter and year:
            quarter_map = {
                "Q1": (f"{year}-01-01", f"{year}-03-31"),
                "Q2": (f"{year}-04-01", f"{year}-06-30"),
                "Q3": (f"{year}-07-01", f"{year}-09-30"),
                "Q4": (f"{year}-10-01", f"{year}-12-31"),
            }
            date_from, date_to = quarter_map[quarter]
        elif year and not (date_from and date_to):
            date_from = f"{year}-01-01"
            date_to = f"{year}-12-31"

        def apply_date_domain(domain, field_name):
            domain = list(domain or [])
            if date_from:
                domain.append((field_name, ">=", date_from))
            if date_to:
                domain.append((field_name, "<=", date_to))
            return domain

        # =========================
        # 2. Sales KPIs
        # =========================
        quotation_domain = apply_date_domain([("state", "in", ["draft", "sent"])], "create_date")
        order_domain = apply_date_domain([("state", "in", ["sale", "done"])], "create_date")

        quotation_count = SaleOrder.search_count(quotation_domain)
        quotation_group = SaleOrder.read_group(quotation_domain, ["amount_total:sum"], [])
        quotation_total_amount = quotation_group[0]["amount_total"] if quotation_group else 0.0

        order_count = SaleOrder.search_count(order_domain)
        order_group = SaleOrder.read_group(order_domain, ["amount_total:sum"], [])
        order_total_amount = order_group[0]["amount_total"] if order_group else 0.0

        conversion_rate = round((order_count / quotation_count) * 100, 2) if quotation_count else 0.0

        top_order_info = {}
        top_order = SaleOrder.search(order_domain, order="amount_total desc", limit=1)
        if top_order:
            top_order_info = {
                "id": top_order.id,
                "name": top_order.name,
                "partner": top_order.partner_id.display_name,
                "amount_total": top_order.amount_total,
            }

        # =========================
        # 3. Top products
        # =========================
        product_line_domain = apply_date_domain(
            [("order_id.state", "in", ["draft", "sent", "sale", "done"])],
            "order_id.create_date",
        )

        product_stats = SaleOrderLine.read_group(
            product_line_domain,
            ["product_id", "product_uom_qty:sum", "price_subtotal:sum"],
            ["product_id"],
            lazy=False,
        )

        product_ids = [x["product_id"][0] for x in product_stats if x.get("product_id")]
        product_orders_map = {}

        if product_ids:
            grouped_orders = SaleOrderLine.read_group(
                product_line_domain + [("product_id", "in", product_ids)],
                ["order_id"],
                ["product_id", "order_id"],
                lazy=False,
            )
            for row in grouped_orders:
                pid = row["product_id"][0]
                oid = row["order_id"][0]
                product_orders_map.setdefault(pid, set()).add(oid)

        top_products = []
        for rec in product_stats:
            if not rec.get("product_id"):
                continue
            pid = rec["product_id"][0]
            product = self.env["product.product"].browse(pid)
            order_ids = list(product_orders_map.get(pid, set()))

            top_products.append({
                "product_id": pid,
                "name": product.display_name,
                "doc_count": len(order_ids),
                "order_ids": order_ids,
                "total_qty": rec.get("product_uom_qty", 0.0),
                "total_amount": rec.get("price_subtotal", 0.0),
            })

        top_products.sort(key=lambda x: (-x["doc_count"], -x["total_amount"]))
        top_products = top_products[:10]

        # =========================
        # 4. Top customers
        # =========================
        quotation_customer_stats = SaleOrder.read_group(
            quotation_domain,
            ["partner_id", "amount_total:sum"],
            ["partner_id"],
            lazy=False,
        )
        order_customer_stats = SaleOrder.read_group(
            order_domain,
            ["partner_id", "amount_total:sum"],
            ["partner_id"],
            lazy=False,
        )

        quotation_map = {}
        for rec in quotation_customer_stats:
            if not rec.get("partner_id"):
                continue
            pid = rec["partner_id"][0]
            quotation_map[pid] = {
                "quotation_count": rec.get("partner_id_count", rec.get("__count", 0)) or 0,
                "quotation_amount": rec.get("amount_total", 0.0) or 0.0,
            }

        customer_combined = {}
        for rec in order_customer_stats:
            if not rec.get("partner_id"):
                continue
            pid = rec["partner_id"][0]
            customer_combined.setdefault(pid, {
                "quotation_count": 0,
                "quotation_amount": 0.0,
                "order_count": 0,
                "order_amount": 0.0,
            })
            customer_combined[pid]["order_count"] = rec.get("partner_id_count", rec.get("__count", 0)) or 0
            customer_combined[pid]["order_amount"] = rec.get("amount_total", 0.0) or 0.0

        for pid, qvals in quotation_map.items():
            customer_combined.setdefault(pid, {
                "quotation_count": 0,
                "quotation_amount": 0.0,
                "order_count": 0,
                "order_amount": 0.0,
            })
            customer_combined[pid]["quotation_count"] = qvals["quotation_count"]
            customer_combined[pid]["quotation_amount"] = qvals["quotation_amount"]

        customer_orders_map = {}
        order_list = SaleOrder.search_read(order_domain, ["id", "partner_id"])
        for rec in order_list:
            if not rec.get("partner_id"):
                continue
            pid = rec["partner_id"][0]
            customer_orders_map.setdefault(pid, []).append(rec["id"])

        top_customers = []
        for pid, vals in customer_combined.items():
            partner = self.env["res.partner"].browse(pid)
            total_docs = vals["quotation_count"] + vals["order_count"]
            total_amount = vals["quotation_amount"] + vals["order_amount"]

            if not total_docs and not total_amount:
                continue

            top_customers.append({
                "partner_id": pid,
                "name": partner.display_name,
                "quotation_count": int(vals["quotation_count"]),
                "order_count": int(vals["order_count"]),
                "quotation_amount": round(vals["quotation_amount"], 2),
                "order_amount": round(vals["order_amount"], 2),
                "total_docs": int(total_docs),
                "total_amount": round(total_amount, 2),
                "order_ids": customer_orders_map.get(pid, []),
            })

        top_customers.sort(key=lambda x: (x["total_docs"], x["total_amount"]), reverse=True)
        top_customers = top_customers[:5]

        # =========================
        # 5. KH-KT / Project data
        # =========================
        expense_records = Expense.search(
            [("total_spent", ">", 0), ("total_cost", ">", 0)],
            limit=5,
            order="total_cost desc",
        )

        project_expense = []
        for rec in expense_records:
            project_expense.append({
                "name": rec.name or (rec.project_id.name or "Không tên"),
                "spent": rec.total_spent or 0.0,
                "not_spent": rec.total_not_spent or 0.0,
                "total": rec.total_cost or 0.0,
                "project_id": rec.project_id.id or False,
            })

        project_domain = []
        if "create_date" in Project._fields:
            project_domain = apply_date_domain([], "create_date")

        all_projects = Project.search(project_domain)
        project_total = len(all_projects)

        project_done = all_projects.filtered(
            lambda p: (
                (getattr(p, "stage_id", False) and (
                    "done" in (p.stage_id.name or "").lower()
                    or "hoàn tất" in (p.stage_id.name or "").lower()
                    or "hoan tat" in (p.stage_id.name or "").lower()
                    or "complete" in (p.stage_id.name or "").lower()
                ))
                or bool(getattr(p, "is_completed", False))
            )
        )
        project_done_count = len(project_done)
        project_in_progress_count = max(project_total - project_done_count, 0)

        khkt_total_budget = sum(x.get("total", 0.0) for x in project_expense)
        khkt_total_spent = sum(x.get("spent", 0.0) for x in project_expense)
        khkt_total_remaining = sum(x.get("not_spent", 0.0) for x in project_expense)

        # =========================
        # 6. Cash flow
        # =========================
        cash_in_domain = apply_date_domain([("state", "=", "posted")], "date")
        cash_out_domain = apply_date_domain([("status_expense", "=", "paid")], "date_payment")

        cash_in = sum(x.get("amount") or 0.0 for x in Receipt.search_read(cash_in_domain, ["amount"]))
        cash_out = sum(x.get("total") or 0.0 for x in PayReq.search_read(cash_out_domain, ["total"]))
        net_cash = cash_in - cash_out

        # =========================
        # 7. Invoices
        # =========================
        supplier_invoice_domain = apply_date_domain([], "date")
        customer_invoice_domain = apply_date_domain([], "date")

        supplier_invoices = SupplierInvoice.search_read(
            supplier_invoice_domain,
            ["id", "invoice_number", "name", "partner_id", "amount", "date", "due_date"],
            order="date desc",
        )
        customer_invoices = CustomerInvoice.search_read(
            customer_invoice_domain,
            ["id", "invoice_number", "name", "partner_id", "amount_total", "date"],
            order="date desc",
        )

        total_supplier_invoice = sum(inv.get("amount") or 0.0 for inv in supplier_invoices)
        total_customer_invoice = sum(inv.get("amount_total") or 0.0 for inv in customer_invoices)

        invoice_overview = {
            "supplier_total": total_supplier_invoice,
            "customer_total": total_customer_invoice,
            "supplier_count": len(supplier_invoices),
            "customer_count": len(customer_invoices),
            "net_invoice": total_customer_invoice - total_supplier_invoice,
        }

        # =========================
        # 8. HR data
        # =========================
        hr_total_employees = 0
        hr_active_employees = 0
        hr_departments = 0
        hr_absent_today = 0

        if "hr.employee" in self.env:
            Employee = self.env["hr.employee"]
            employee_domain = []
            if "create_date" in Employee._fields:
                employee_domain = apply_date_domain([], "create_date")

            employees = Employee.search(employee_domain)
            hr_total_employees = len(employees)

            if "active" in Employee._fields:
                hr_active_employees = Employee.search_count(employee_domain + [("active", "=", True)])
            else:
                hr_active_employees = hr_total_employees

            if "department_id" in Employee._fields:
                dept_ids = employees.mapped("department_id").ids
                hr_departments = len(dept_ids)

            # nghỉ phép / vắng hôm nay
            if "hr.leave" in self.env:
                Leave = self.env["hr.leave"]
                today = fields.Date.context_today(self)

                leave_domain = [
                    ("state", "=", "validate"),
                    ("request_date_from", "<=", today),
                    ("request_date_to", ">=", today),
                ]
                if "employee_id" in Leave._fields and hr_total_employees:
                    hr_absent_today = Leave.search_count(leave_domain)

        elif "res.users" in self.env:
            Users = self.env["res.users"]
            users = Users.search([("share", "=", False)])
            hr_total_employees = len(users)
            hr_active_employees = len(users.filtered(lambda u: u.active))
            hr_departments = 0
            hr_absent_today = 0
        # =========================
        # 8. Approval / Chờ giám đốc duyệt
        # =========================
        proposal_pending_domain = apply_date_domain(
            [("state", "=", "approved")],
            "create_date",
        )

        payment_pending_domain = apply_date_domain(
            [("state", "=", "account_approved")],
            "create_date",
        )

        proposal_pending_records = ProposalSheet.search(
            proposal_pending_domain,
            order="create_date desc",
            limit=5,
        )

        payment_pending_records = PaymentProposal.search(
            payment_pending_domain,
            order="create_date desc",
            limit=5,
        )

        proposal_pending_count = ProposalSheet.search_count(proposal_pending_domain)
        payment_pending_count = PaymentProposal.search_count(payment_pending_domain)

        proposal_pending_amount = sum(proposal_pending_records.mapped("amount_total_taxes")) if proposal_pending_records else 0.0
        payment_pending_amount = sum(payment_pending_records.mapped("amount_remain")) if payment_pending_records else 0.0

        approval_pending_count = proposal_pending_count + payment_pending_count
        approval_pending_amount = proposal_pending_amount + payment_pending_amount

        approval_pending_items = []

        for rec in proposal_pending_records:
            approval_pending_items.append({
                "type": "proposal_sheet",
                "type_label": "Phiếu đề xuất",
                "id": rec.id,
                "name": rec.name,
                "date": rec.create_date.strftime("%Y-%m-%d") if rec.create_date else "",
                "user_name": rec.requested_by.name if rec.requested_by else "",
                "department_name": rec.department_id.name if rec.department_id else "",
                "project_name": rec.project_id.name if rec.project_id else "",
                "state": rec.state,
                "state_label": "Chờ giám đốc duyệt",
                "amount": rec.amount_total_taxes or rec.amount_total or 0.0,
            })

        for rec in payment_pending_records:
            approval_pending_items.append({
                "type": "payment_proposal",
                "type_label": "Phiếu giải chi",
                "id": rec.id,
                "name": rec.name,
                "date": rec.create_date.strftime("%Y-%m-%d") if rec.create_date else "",
                "user_name": rec.user_id.name if rec.user_id else "",
                "department_name": rec.department_id.name if rec.department_id else "",
                "project_name": rec.project_id.name if rec.project_id else "",
                "state": rec.state,
                "state_label": "Chờ giám đốc duyệt",
                "amount": rec.amount_remain or rec.total_amount or 0.0,
            })

        approval_pending_items.sort(key=lambda x: x.get("date") or "", reverse=True)
        approval_pending_items = approval_pending_items[:10]
        

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
                "net_cash": net_cash,
            },
            "invoice_overview": invoice_overview,
            "top_products": top_products,
            "top_customers": top_customers,
            "project_expense": project_expense,
            "top_order": top_order_info,
            "conversion_rate": conversion_rate,

            # KH-KT
            "project_total": project_total,
            "project_done_count": project_done_count,
            "project_in_progress_count": project_in_progress_count,
            "khkt_total_budget": khkt_total_budget,
            "khkt_total_spent": khkt_total_spent,
            "khkt_total_remaining": khkt_total_remaining,

            # HR
            "hr_total_employees": hr_total_employees,
            "hr_active_employees": hr_active_employees,
            "hr_departments": hr_departments,
            "hr_absent_today": hr_absent_today,
            "approval_summary": {
                "proposal_pending_count": proposal_pending_count,
                "payment_pending_count": payment_pending_count,
                "pending_count": approval_pending_count,
                "proposal_pending_amount": proposal_pending_amount,
                "payment_pending_amount": payment_pending_amount,
                "pending_amount": approval_pending_amount,
            },
            "approval_pending_items": approval_pending_items,

            "date_from": date_from,
            "date_to": date_to,
            "year": year,
            "quarter": quarter,
        }