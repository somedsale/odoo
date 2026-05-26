# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools.misc import xlsxwriter

from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict

import io
import base64
import datetime


class MonthlyRevenueExpenseReport(models.TransientModel):
    _name = "monthly.revenue.expense.report"
    _description = "Báo cáo doanh thu - chi phí hàng tháng"

    period_type = fields.Selection(
        [
            ("month", "Theo tháng"),
            ("quarter", "Theo quý"),
            ("year", "Theo năm"),
        ],
        string="Kỳ báo cáo",
        required=True,
        default="month",
    )

    quarter = fields.Selection(
        [
            ("1", "Quý I"),
            ("2", "Quý II"),
            ("3", "Quý III"),
            ("4", "Quý IV"),
        ],
        string="Quý",
    )

    month = fields.Selection(
        [(str(m), f"Tháng {m}") for m in range(1, 13)],
        string="Tháng",
        required=True,
        default=lambda self: str(date.today().month),
    )

    year = fields.Integer(
        string="Năm",
        required=True,
        default=lambda self: date.today().year,
    )

    # =========================================================
    # DATE RANGE - WIZARD
    # =========================================================
    def _get_date_range(self):
        self.ensure_one()

        year = int(self.year)

        if self.period_type == "month":
            month = int(self.month)
            date_from = date(year, month, 1)
            date_to = date_from + relativedelta(months=1, days=-1)

        elif self.period_type == "quarter":
            if not self.quarter:
                raise UserError(_("Vui lòng chọn Quý"))

            q = int(self.quarter)
            month_from = (q - 1) * 3 + 1
            date_from = date(year, month_from, 1)
            date_to = date_from + relativedelta(months=3, days=-1)

        else:
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)

        return date_from, date_to

    # =========================================================
    # DATE RANGE - OWL FILTER
    # =========================================================
    @api.model
    def _get_date_range_from_filters(self, filters=None):
        filters = filters or {}

        period_type = filters.get("period_type") or "month"
        year = int(filters.get("year") or date.today().year)

        if period_type == "month":
            month = int(filters.get("month") or date.today().month)
            date_from = date(year, month, 1)
            date_to = date_from + relativedelta(months=1, days=-1)

        elif period_type == "quarter":
            quarter = int(filters.get("quarter") or 1)
            month_from = (quarter - 1) * 3 + 1
            date_from = date(year, month_from, 1)
            date_to = date_from + relativedelta(months=3, days=-1)

        else:
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)

        return date_from, date_to

    # =========================================================
    # OPEN OWL REPORT FROM WIZARD
    # =========================================================
    def action_view_report(self):
        self.ensure_one()

        return {
            "type": "ir.actions.client",
            "tag": "monthly_revenue_expense_report.owl_report",
            "name": "Báo cáo Doanh thu - Chi phí",
            "target": "current",
            "params": {
                "filters": {
                    "period_type": self.period_type,
                    "month": self.month,
                    "quarter": self.quarter,
                    "year": self.year,
                }
            },
        }

    # =========================================================
    # CREATE TEMP WIZARD FROM OWL FILTERS
    # =========================================================
    @api.model
    def _create_wizard_from_filters(self, filters=None):
        filters = filters or {}

        period_type = filters.get("period_type") or "month"
        month = filters.get("month") or str(date.today().month)
        quarter = filters.get("quarter") or "1"
        year = int(filters.get("year") or date.today().year)

        vals = {
            "period_type": period_type,
            "year": year,
        }

        if period_type == "month":
            vals["month"] = str(month)

        elif period_type == "quarter":
            vals["quarter"] = str(quarter)

        return self.create(vals)

    # =========================================================
    # DATA FOR OWL REPORT
    # =========================================================
    @api.model
    def get_owl_report_data(self, filters=None):
        filters = filters or {}

        period_type = filters.get("period_type") or "month"
        month = filters.get("month") or str(date.today().month)
        quarter = filters.get("quarter") or "1"
        year = int(filters.get("year") or date.today().year)

        date_from, date_to = self._get_date_range_from_filters({
            "period_type": period_type,
            "month": month,
            "quarter": quarter,
            "year": year,
        })

        report_model = self.env["report.monthly_revenue_expense_report.report_template"]

        vals = report_model._get_report_values([], data={
            "period_type": period_type,
            "month": month,
            "quarter": quarter,
            "year": year,
            "date_from": date_from,
            "date_to": date_to,
        })

        if period_type == "month":
            period_label = f"THÁNG {month} NĂM {year}"
        elif period_type == "quarter":
            period_label = f"QUÝ {quarter} NĂM {year}"
        else:
            period_label = f"NĂM {year}"

        company = self.env.company

        company_address = ", ".join(filter(None, [
            company.street,
            company.street2,
            company.city,
            company.state_id.name if company.state_id else None,
            company.country_id.name if company.country_id else None,
        ]))

        return {
            "filters": {
                "period_type": period_type,
                "month": month,
                "quarter": quarter,
                "year": year,
            },
            "period_label": period_label,
            "company": {
                "id": company.id,
                "name": company.name or "",
                "vat": company.vat or "",
                "address": company_address,
                "logo_url": f"/web/image/res.company/{company.id}/logo",
            },
            "period_type": vals.get("period_type"),
            "month": vals.get("month"),
            "quarter": vals.get("quarter"),
            "year": vals.get("year"),
            "start_date": str(vals.get("start_date")),
            "end_date": str(vals.get("end_date")),
            "revenue_data": vals.get("revenue_data") or [],
            "expense_data": vals.get("expense_data") or [],
            "total_revenue": vals.get("total_revenue") or 0.0,
            "total_expense": vals.get("total_expense") or 0.0,
            "net_profit": vals.get("net_profit") or 0.0,
        }

    # =========================================================
    # UPDATE EXPENSE BUCKET NAME FROM OWL
    # =========================================================
    @api.model
    def update_expense_bucket_name(self, bucket_id, new_name):
        if not bucket_id:
            raise UserError(_("Thiếu khoản mục cần sửa."))

        new_name = (new_name or "").strip()

        if not new_name:
            raise UserError(_("Tên khoản mục không được để trống."))

        bucket = self.env["account.payment.request.expense.bucket"].browse(int(bucket_id)).exists()

        if not bucket:
            raise UserError(_("Không tìm thấy khoản mục báo cáo."))

        bucket.write({
            "name": new_name,
        })

        return {
            "success": True,
            "bucket_id": bucket.id,
            "name": bucket.name,
        }

    # =========================================================
    # EXPORT EXCEL FROM OWL FILTERS
    # =========================================================
    @api.model
    def action_export_excel_from_filters(self, filters=None):
        wizard = self._create_wizard_from_filters(filters)
        return wizard.action_export_excel()

    # =========================================================
    # EXPORT PDF FROM OWL FILTERS
    # =========================================================
    @api.model
    def action_export_pdf_from_filters(self, filters=None):
        wizard = self._create_wizard_from_filters(filters)

        date_from, date_to = wizard._get_date_range()

        data = {
            "period_type": wizard.period_type,
            "month": wizard.month,
            "quarter": wizard.quarter,
            "year": wizard.year,
            "date_from": date_from,
            "date_to": date_to,
        }

        return self.env.ref(
            "monthly_revenue_expense_report.report_monthly_revenue_expense_action_pdf"
        ).report_action(wizard, data=data)

    # =========================================================
    # EXPORT EXCEL
    # =========================================================
    def action_export_excel(self):
        self.ensure_one()

        report_model = self.env["report.monthly_revenue_expense_report.report_template"]
        date_from, date_to = self._get_date_range()

        vals = report_model._get_report_values([], data={
            "period_type": self.period_type,
            "month": self.month,
            "quarter": self.quarter,
            "year": self.year,
            "date_from": date_from,
            "date_to": date_to,
        })

        period_type = vals.get("period_type")
        year = int(vals.get("year") or self.year)

        if period_type == "month":
            month = int(vals.get("month") or self.month)
            period_label = f"THÁNG {month} NĂM {year}"
            period_code = f"T{month}-{year}"

        elif period_type == "quarter":
            quarter = vals.get("quarter") or self.quarter
            period_label = f"QUÝ {quarter} NĂM {year}"
            period_code = f"Q{quarter}-{year}"

        else:
            period_label = f"NĂM {year}"
            period_code = f"Y{year}"

        revenue_data = vals.get("revenue_data") or []
        expense_data = vals.get("expense_data") or []

        company = self.env.company
        company_name = company.name or ""

        company_address = ", ".join(filter(None, [
            company.street,
            company.street2,
            company.city,
            company.state_id.name if company.state_id else None,
            company.country_id.name if company.country_id else None,
        ]))

        company_vat = company.vat or ""

        def init_formats(wb):
            return {
                "fmt_company_name": wb.add_format({
                    "bold": True,
                    "font_size": 11,
                }),
                "fmt_company_info": wb.add_format({
                    "font_size": 10,
                }),
                "fmt_title": wb.add_format({
                    "bold": True,
                    "font_size": 16,
                    "align": "center",
                    "valign": "vcenter",
                }),
                "fmt_group": wb.add_format({
                    "bold": True,
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#E2EFDA",
                }),
                "fmt_head": wb.add_format({
                    "bold": True,
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                    "bg_color": "#C6E0B4",
                    "text_wrap": True,
                }),
                "fmt_stt": wb.add_format({
                    "border": 1,
                    "align": "center",
                    "valign": "vcenter",
                }),
                "fmt_text_left": wb.add_format({
                    "border": 1,
                    "align": "left",
                    "valign": "top",
                    "text_wrap": True,
                }),
                "fmt_money": wb.add_format({
                    "border": 1,
                    "num_format": "#,##0",
                    "align": "right",
                    "valign": "vcenter",
                }),
                "fmt_money_bold": wb.add_format({
                    "border": 1,
                    "num_format": "#,##0",
                    "bold": True,
                    "align": "right",
                    "valign": "vcenter",
                }),
            }

        output = io.BytesIO()
        wb = xlsxwriter.Workbook(output, {"in_memory": True})
        ws = wb.add_worksheet(period_code)
        F = init_formats(wb)

        ws.set_column("A:A", 6)
        ws.set_column("B:B", 70)
        ws.set_column("C:C", 20)
        ws.set_column("D:D", 20)
        ws.set_column("E:E", 22)

        if company.logo:
            ws.insert_image(
                0,
                0,
                "logo.png",
                {
                    "image_data": io.BytesIO(base64.b64decode(company.logo)),
                    "x_scale": 0.45,
                    "y_scale": 0.45,
                },
            )

        ws.merge_range(0, 2, 0, 6, company_name, F["fmt_company_name"])
        ws.merge_range(1, 2, 1, 6, f"Địa chỉ: {company_address}", F["fmt_company_info"])
        ws.merge_range(2, 2, 2, 6, f"MST: {company_vat}", F["fmt_company_info"])

        ws.merge_range(
            4,
            0,
            4,
            6,
            f"BÁO CÁO DOANH THU - CHI PHÍ {period_label}",
            F["fmt_title"],
        )
        ws.set_row(4, 36)

        row = 6

        ws.write_row(
            row,
            0,
            ["STT", "Nội dung", "Doanh thu", "Chi phí", "Chênh lệch"],
            F["fmt_head"],
        )
        ws.set_row(row, 26)
        ws.freeze_panes(row + 1, 0)
        row += 1

        total_revenue = vals.get("total_revenue", 0.0) or 0.0
        total_expense = vals.get("total_expense", 0.0) or 0.0
        net_profit = total_revenue - total_expense

        ws.merge_range(row, 0, row, 1, "TỔNG CỘNG", F["fmt_group"])
        ws.write(row, 2, total_revenue, F["fmt_money_bold"])
        ws.write(row, 3, total_expense, F["fmt_money_bold"])
        ws.write(row, 4, net_profit, F["fmt_money_bold"])
        ws.set_row(row, 28)
        row += 1

        # I. DOANH THU
        ws.merge_range(row, 0, row, 1, "I. DOANH THU", F["fmt_group"])
        ws.write(row, 2, total_revenue, F["fmt_money_bold"])
        ws.write(row, 3, 0, F["fmt_money_bold"])
        ws.write(row, 4, total_revenue, F["fmt_money_bold"])
        row += 1

        stt = 1

        for grp in revenue_data:
            subtotal = grp.get("subtotal", 0.0) or 0.0

            ws.merge_range(row, 0, row, 1, grp.get("type_label", ""), F["fmt_group"])
            ws.write(row, 2, subtotal, F["fmt_money_bold"])
            ws.write(row, 3, 0, F["fmt_money_bold"])
            ws.write(row, 4, subtotal, F["fmt_money_bold"])
            row += 1

            for line in grp.get("projects", []):
                revenue = line.get("revenue", 0.0) or 0.0

                ws.write(row, 0, stt, F["fmt_stt"])
                ws.write(row, 1, line.get("name", ""), F["fmt_text_left"])
                ws.write(row, 2, revenue, F["fmt_money"])
                ws.write(row, 3, 0, F["fmt_money"])
                ws.write(row, 4, revenue, F["fmt_money"])
                row += 1
                stt += 1

        row += 1

        # II. CHI PHÍ
        ws.merge_range(row, 0, row, 1, "II. CHI PHÍ", F["fmt_group"])
        ws.write(row, 2, 0, F["fmt_money_bold"])
        ws.write(row, 3, total_expense, F["fmt_money_bold"])
        ws.write(row, 4, -total_expense, F["fmt_money_bold"])
        row += 1

        stt = 1

        for grp in expense_data:
            subtotal = grp.get("subtotal", 0.0) or 0.0

            ws.merge_range(row, 0, row, 1, grp.get("type_label", ""), F["fmt_group"])
            ws.write(row, 2, 0, F["fmt_money_bold"])
            ws.write(row, 3, subtotal, F["fmt_money_bold"])
            ws.write(row, 4, -subtotal, F["fmt_money_bold"])
            row += 1

            if grp.get("subgroups"):
                for sub in grp.get("subgroups", []):
                    sub_total = sub.get("subtotal", 0.0) or 0.0

                    ws.merge_range(row, 0, row, 1, sub.get("sub_label", ""), F["fmt_group"])
                    ws.write(row, 2, 0, F["fmt_money_bold"])
                    ws.write(row, 3, sub_total, F["fmt_money_bold"])
                    ws.write(row, 4, -sub_total, F["fmt_money_bold"])
                    row += 1

                    for line in sub.get("lines", []):
                        expense = line.get("expense", 0.0) or 0.0

                        ws.write(row, 0, stt, F["fmt_stt"])
                        ws.write(row, 1, line.get("name", ""), F["fmt_text_left"])
                        ws.write(row, 2, 0, F["fmt_money"])
                        ws.write(row, 3, expense, F["fmt_money"])
                        ws.write(row, 4, -expense, F["fmt_money"])
                        row += 1
                        stt += 1

            else:
                for line in grp.get("lines", []):
                    expense = line.get("expense", 0.0) or 0.0

                    ws.write(row, 0, stt, F["fmt_stt"])
                    ws.write(row, 1, line.get("name", ""), F["fmt_text_left"])
                    ws.write(row, 2, 0, F["fmt_money"])
                    ws.write(row, 3, expense, F["fmt_money"])
                    ws.write(row, 4, -expense, F["fmt_money"])
                    row += 1
                    stt += 1

            row += 1

        wb.close()
        output.seek(0)

        filename = f"BAO_CAO_DOANH_THU_CHI_PHI_{period_code}.xlsx"

        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "description": "TEMP_EXPORT_EXCEL",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }


class AccountReceiptReport(models.AbstractModel):
    _name = "report.monthly_revenue_expense_report.report_template"
    _description = "Render báo cáo doanh thu - chi phí hàng tháng"

    def _to_date_string(self, value):
        if not value:
            return False

        if isinstance(value, str):
            return value

        return fields.Date.to_string(value)

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}

        start_date = data.get("date_from")
        end_date = data.get("date_to")

        if not start_date or not end_date:
            raise UserError(_("Thiếu khoảng thời gian báo cáo"))

        start_date_str = self._to_date_string(start_date)
        end_date_str = self._to_date_string(end_date)

        month = data.get("month")
        year = data.get("year")
        quarter = data.get("quarter")
        period_type = data.get("period_type")

        receipt_base_domain = [
            ["date", ">=", start_date_str],
            ["date", "<=", end_date_str],
            ["state", "=", "posted"],
        ]

        payment_base_domain = [
            ["date_payment", ">=", start_date_str],
            ["date_payment", "<=", end_date_str],
            ["state", "in", ["post", "done"]],
        ]

        # =====================================================
        # DOANH THU
        # =====================================================
        receipts = self.env["account.receipt"].search(receipt_base_domain)

        rev_grouped = defaultdict(lambda: defaultdict(float))
        rev_domains = defaultdict(dict)

        for r in receipts:
            tkey = r.type_revenue or "unknown"

            if tkey in ("done_revenue", "advance"):
                if not r.project_id:
                    continue

                line_key = f"project_{r.project_id.id}"
                line_name = r.project_id.name

                domain = receipt_base_domain + [
                    ["type_revenue", "=", tkey],
                    ["project_id", "=", r.project_id.id],
                ]

                rev_grouped[tkey][line_key] += r.amount or 0.0
                rev_domains[tkey][line_key] = {
                    "name": line_name,
                    "domain": domain,
                }

            elif tkey in ("loan", "other"):
                if r.project_id:
                    line_key = f"project_{r.project_id.id}"
                    line_name = r.project_id.name

                    domain = receipt_base_domain + [
                        ["type_revenue", "=", tkey],
                        ["project_id", "=", r.project_id.id],
                    ]
                else:
                    note = r.note or _("(Không có nội dung)")
                    line_key = f"note_{note}"
                    line_name = note

                    if r.note:
                        domain = receipt_base_domain + [
                            ["type_revenue", "=", tkey],
                            ["project_id", "=", False],
                            ["note", "=", r.note],
                        ]
                    else:
                        domain = receipt_base_domain + [
                            ["type_revenue", "=", tkey],
                            ["project_id", "=", False],
                            ["note", "=", False],
                        ]

                rev_grouped[tkey][line_key] += r.amount or 0.0
                rev_domains[tkey][line_key] = {
                    "name": line_name,
                    "domain": domain,
                }

            else:
                continue

        rev_order = [
            ("done_revenue", "A. Doanh thu đã thực hiện"),
            ("advance", "B. Doanh thu chưa thực hiện (Tạm ứng)"),
            ("other", "C. Các khoản thu khác"),
            ("loan", "D. Các khoản vay"),
        ]

        revenue_data = []

        for key, label in rev_order:
            project_lines = rev_grouped.get(key, {})
            total = sum(project_lines.values())

            if key in ("done_revenue", "advance"):
                group_domain = receipt_base_domain + [
                    ["type_revenue", "=", key],
                    ["project_id", "!=", False],
                ]
            else:
                group_domain = receipt_base_domain + [
                    ["type_revenue", "=", key],
                ]

            revenue_data.append({
                "type_key": key,
                "type_label": label,
                "subtotal": total,
                "model": "account.receipt",
                "domain": group_domain,
                "projects": [
                    {
                        "name": rev_domains[key][line_key]["name"],
                        "revenue": amount,
                        "model": "account.receipt",
                        "domain": rev_domains[key][line_key]["domain"],
                    }
                    for line_key, amount in project_lines.items()
                ],
            })

        # =====================================================
        # CHI PHÍ - KHOẢN MỤC ĐỘNG
        # =====================================================
        payments = self.env["account.payment.request"].search(payment_base_domain)

        Bucket = self.env["account.payment.request.expense.bucket"]

        fixed_buckets = Bucket.search([
            ["section", "=", "fixed"],
            ["active", "=", True],
        ], order="sequence, id")

        company_buckets = Bucket.search([
            ["section", "=", "company"],
            ["active", "=", True],
        ], order="sequence, id")

        A_IDS = fixed_buckets.ids
        B_IDS = company_buckets.ids
        A_CODES = fixed_buckets.mapped("code")
        B_CODES = company_buckets.mapped("code")

        def _payment_match_bucket(payment, bucket):
            if payment.expense_bucket_id:
                return payment.expense_bucket_id.id == bucket.id

            return payment.expense_bucket == bucket.code

        def _sum_bucket(bucket):
            total = 0.0

            for payment in payments:
                if _payment_match_bucket(payment, bucket):
                    total += payment.total or 0.0

            return total

        def _bucket_domain(bucket):
            return expression.AND([
                payment_base_domain,
                expression.OR([
                    [["expense_bucket_id", "=", bucket.id]],
                    [["expense_bucket", "=", bucket.code]],
                ]),
            ])

        fixed_domain = expression.AND([
            payment_base_domain,
            expression.OR([
                [["expense_bucket_id", "in", A_IDS]],
                [["expense_bucket", "in", A_CODES]],
            ]),
        ])

        company_domain = expression.AND([
            payment_base_domain,
            expression.OR([
                [["expense_bucket_id", "in", B_IDS]],
                [["expense_bucket", "in", B_CODES]],
            ]),
        ])

        A_LINES = [
            {
                "bucket_id": bucket.id,
                "key": bucket.code,
                "name": bucket.name,
                "expense": _sum_bucket(bucket),
                "model": "account.payment.request",
                "domain": _bucket_domain(bucket),
                "can_edit_name": True,
            }
            for bucket in fixed_buckets
        ]

        B_LINES = [
            {
                "bucket_id": bucket.id,
                "key": bucket.code,
                "name": bucket.name,
                "expense": _sum_bucket(bucket),
                "model": "account.payment.request",
                "domain": _bucket_domain(bucket),
                "can_edit_name": True,
            }
            for bucket in company_buckets
        ]

        # =====================================================
        # B/b. CHI PHÍ CÔNG TRÌNH
        # =====================================================
        project_costs = defaultdict(float)
        project_cost_domains = {}

        for p in payments.filtered(lambda x: x.cost_classification == "project"):
            if p.project_id:
                line_key = f"project_{p.project_id.id}"
                line_name = p.project_id.name
                line_domain = payment_base_domain + [
                    ["cost_classification", "=", "project"],
                    ["project_id", "=", p.project_id.id],
                ]
            else:
                line_key = "no_project"
                line_name = _("(Không có dự án)")
                line_domain = payment_base_domain + [
                    ["cost_classification", "=", "project"],
                    ["project_id", "=", False],
                ]

            project_costs[line_key] += p.total or 0.0
            project_cost_domains[line_key] = {
                "name": line_name,
                "domain": line_domain,
            }

        project_cost_lines = [
            {
                "name": project_cost_domains[line_key]["name"],
                "expense": amount,
                "model": "account.payment.request",
                "domain": project_cost_domains[line_key]["domain"],
                "can_edit_name": False,
            }
            for line_key, amount in project_costs.items()
        ]

        # =====================================================
        # C. BIẾN PHÍ KHÔNG THƯỜNG XUYÊN
        # =====================================================
        irregular_costs = defaultdict(float)
        irregular_cost_domains = {}

        for p in payments.filtered(lambda x: x.cost_classification == "irregular_expenses"):
            if p.expense_category_id:
                line_key = f"category_{p.expense_category_id.id}"
                line_name = p.expense_category_id.name
                line_domain = payment_base_domain + [
                    ["cost_classification", "=", "irregular_expenses"],
                    ["expense_category_id", "=", p.expense_category_id.id],
                ]
            else:
                line_key = "no_category"
                line_name = _("(Không có khoản mục)")
                line_domain = payment_base_domain + [
                    ["cost_classification", "=", "irregular_expenses"],
                    ["expense_category_id", "=", False],
                ]

            irregular_costs[line_key] += p.total or 0.0
            irregular_cost_domains[line_key] = {
                "name": line_name,
                "domain": line_domain,
            }

        irregular_cost_lines = [
            {
                "name": irregular_cost_domains[line_key]["name"],
                "expense": amount,
                "model": "account.payment.request",
                "domain": irregular_cost_domains[line_key]["domain"],
                "can_edit_name": False,
            }
            for line_key, amount in irregular_costs.items()
        ]

        group_b_domain = expression.AND([
            payment_base_domain,
            expression.OR([
                [["expense_bucket_id", "in", B_IDS]],
                [["expense_bucket", "in", B_CODES]],
                [["cost_classification", "=", "project"]],
            ]),
        ])

        expense_data = [
            {
                "type_label": "A. TỔNG ĐỊNH PHÍ",
                "model": "account.payment.request",
                "domain": fixed_domain,
                "lines": A_LINES,
                "subtotal": sum(x["expense"] for x in A_LINES),
            },
            {
                "type_label": "B. TỔNG BIẾN PHÍ THƯỜNG XUYÊN",
                "model": "account.payment.request",
                "domain": group_b_domain,
                "subgroups": [
                    {
                        "sub_label": "a. Chi phí công ty",
                        "model": "account.payment.request",
                        "domain": company_domain,
                        "lines": B_LINES,
                        "subtotal": sum(x["expense"] for x in B_LINES),
                    },
                    {
                        "sub_label": "b. Chi phí công trình",
                        "model": "account.payment.request",
                        "domain": payment_base_domain + [
                            ["cost_classification", "=", "project"],
                        ],
                        "lines": project_cost_lines,
                        "subtotal": sum(project_costs.values()),
                    },
                ],
                "subtotal": sum(x["expense"] for x in B_LINES) + sum(project_costs.values()),
            },
            {
                "type_label": "C. TỔNG BIẾN PHÍ KHÔNG THƯỜNG XUYÊN",
                "model": "account.payment.request",
                "domain": payment_base_domain + [
                    ["cost_classification", "=", "irregular_expenses"],
                ],
                "lines": irregular_cost_lines,
                "subtotal": sum(irregular_costs.values()),
            },
        ]

        total_revenue = sum(
            (r.amount or 0.0)
            for r in receipts
            if r.type_revenue not in ("explain",)
        )

        total_expense = sum(
            (p.total or 0.0)
            for p in payments
        )

        net_profit = total_revenue - total_expense

        return {
            "doc_ids": docids,
            "doc_model": "monthly.revenue.expense.report",
            "docs": self.env["monthly.revenue.expense.report"].browse(docids),
            "res_company": self.env.company,
            "company": self.env.company,
            "user_id": self.env.user,
            "env": self.env,
            "datetime": datetime,
            "period_type": period_type,
            "quarter": quarter,
            "month": month,
            "year": year,
            "start_date": start_date_str,
            "end_date": end_date_str,
            "revenue_data": revenue_data,
            "expense_data": expense_data,
            "total_revenue": total_revenue,
            "total_expense": total_expense,
            "net_profit": net_profit,
        }