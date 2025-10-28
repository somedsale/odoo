# -*- coding: utf-8 -*-
from odoo import models, api
from collections import defaultdict
from datetime import datetime, date


class TaxReport(models.AbstractModel):
    _name = "report.tax_report_summary.tax_report_template"
    _description = "Tax Report Summary (Grouped by Date or Month + Partner)"

    @api.model
    def _get_report_values(self, docids, data=None):
        """Trả dữ liệu cho báo cáo thuế — nhóm theo ngày hoặc theo tháng (với gộp theo đối tượng)"""
        date_from = data.get("date_from") if data else None
        date_to = data.get("date_to") if data else None
        view_type = data.get("view_type", "period")

        # -----------------------------
        # Chuẩn hóa ngày
        # -----------------------------
        def parse_date(value):
            if not value:
                return None
            if isinstance(value, date):
                return value
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except Exception:
                return None

        date_from = parse_date(date_from)
        date_to = parse_date(date_to)

        domain = []
        if date_from and date_to:
            domain = [("date", ">=", date_from), ("date", "<=", date_to)]

        # -----------------------------
        # Lấy hóa đơn có số
        # -----------------------------
        supplier_invoices = self.env["supplier.invoice"].search(
            domain + [("invoice_number", "!=", False), ("invoice_number", "!=", "")],
            order="date asc",
        )
        customer_invoices = self.env["customer.invoice"].search(
            domain + [("invoice_number", "!=", False), ("invoice_number", "!=", "")],
            order="date asc",
        )

        # -----------------------------
        # Gom nhóm
        # -----------------------------
        grouped = defaultdict(lambda: {"supplier": [], "customer": []})

        if view_type == "year":
            # Gom theo tháng và đối tượng (partner)
            monthly_sup = defaultdict(lambda: defaultdict(float))
            monthly_cus = defaultdict(lambda: defaultdict(float))

            for s in supplier_invoices:
                if not s.date:
                    continue
                month_key = s.date.strftime("%Y-%m")
                partner_name = s.partner_id.name or "Không xác định"
                monthly_sup[month_key][partner_name] += s.amount_tax or 0.0

            for c in customer_invoices:
                if not c.date:
                    continue
                month_key = c.date.strftime("%Y-%m")
                partner_name = c.partner_id.name or "Không xác định"
                monthly_cus[month_key][partner_name] += c.amount_tax or 0.0

            # Đưa dữ liệu vào grouped
            for m in sorted(set(list(monthly_sup.keys()) + list(monthly_cus.keys()))):
                grouped[m]["supplier"] = [
                    {"partner": k, "amount_tax": v} for k, v in monthly_sup[m].items()
                ]
                grouped[m]["customer"] = [
                    {"partner": k, "amount_tax": v} for k, v in monthly_cus[m].items()
                ]

            sorted_dates = sorted(grouped.keys())

        else:
            # Gom theo ngày (chi tiết)
            for s in supplier_invoices:
                grouped[s.date]["supplier"].append(s)
            for c in customer_invoices:
                grouped[c.date]["customer"].append(c)
            sorted_dates = sorted(grouped.keys())

        # -----------------------------
        # Tổng cộng toàn kỳ
        # -----------------------------
        total_supplier_tax = sum(s.amount_tax for s in supplier_invoices)
        total_customer_tax = sum(c.amount_tax for c in customer_invoices)
        tax_diff = total_supplier_tax - total_customer_tax  # Vào - Ra

        # -----------------------------
        # Trả kết quả
        # -----------------------------
        return {
            "date_from": date_from,
            "date_to": date_to,
            "view_type": view_type,
            "grouped": grouped,
            "sorted_dates": sorted_dates,
            "total_supplier_tax": total_supplier_tax,
            "total_customer_tax": total_customer_tax,
            "tax_diff": tax_diff,
        }
