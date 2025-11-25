# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, date


class InputTaxReport(models.AbstractModel):
    _name = "report.tax_report_summary.input_tax_report_template"
    _description = "Input Tax Report Summary (Supplier invoices only)"

    @api.model
    def _get_report_values(self, docids, data=None):

        date_from = data.get("date_from")
        date_to = data.get("date_to")
        view_type = data.get("view_type")
        year = data.get("year")
        month = data.get("month")
        quarter = data.get("quarter")
        title = "BÁO CÁO HÓA ĐƠN ĐẦU VÀO"
        if view_type == "month" and month:
            title += f" THÁNG {month} NĂM {year}"
        elif view_type == "quarter" and quarter:
            title += f" QUÝ {quarter} NĂM {year}"
        elif view_type == "year":
            title += f" NĂM {year}"
        # ---- Hàm parse ngày ----
        def parse_date(v):
            if not v:
                return None
            if isinstance(v, date):
                return v
            try:
                return datetime.strptime(v, "%Y-%m-%d").date()
            except:
                return None

        date_from = parse_date(date_from)
        date_to = parse_date(date_to)

        # ---- Domain lọc hóa đơn có số ----
        domain = [
            ("invoice_number", "!=", False),
            ("invoice_number", "!=", ""),
        ]

        if date_from and date_to:
            domain += [("date", ">=", date_from), ("date", "<=", date_to)]

        # ---- Lấy hóa đơn ----
        invoices = self.env["supplier.invoice"].search(domain, order="date asc")

        rows = []
        for idx, inv in enumerate(invoices, start=1):

            before_tax = inv.amount - inv.amount_tax
            total = inv.amount
            tax_percent = 0
            if before_tax > 0:
                tax_percent = inv.amount_tax / before_tax * 100

            rows.append({
                "stt": idx,
                "date": inv.date,
                "invoice_number": inv.invoice_number,
                "partner": inv.partner_id.name,
                "before_tax": before_tax,
                "tax_amount": inv.amount_tax,
                "total": total,
                "tax_percent": tax_percent,

                # ================================
                # DÙNG CHO (theo cost_classification)
                # ================================
                "used_for":
                    inv.project_id.name
                    if inv.cost_classification == "project"
                    else (inv.expense_category_id.name or ""),
                "is_warehouse":
                    "Nhập kho" if inv.is_warehouse == "warehouse"
                    else ("Công trình" if inv.is_warehouse == "contruction" else ""),
                "note": inv.note or "",
            })


        return {
            "rows": rows,
            "date_from": date_from,
            "date_to": date_to,
            'title': title,
            "total_before": sum(r["before_tax"] for r in rows),
            "total_tax": sum(r["tax_amount"] for r in rows),
            "total_sum": sum(r["total"] for r in rows),
        }
