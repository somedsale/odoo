# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date, timedelta
import calendar
import io
import base64
from odoo.tools.misc import xlsxwriter


class DailyCashFlowWizard(models.TransientModel):
    _name = "daily.cash.flow.wizard"
    _description = "Cash Flow Report Wizard / OWL Service"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    period_type = fields.Selection(
        [
            ("custom", "Khoảng ngày"),
            ("month", "Tháng"),
            ("quarter", "Quý"),
            ("year", "Năm"),
        ],
        default="custom",
        required=True,
    )

    date_from = fields.Date(string="Từ ngày", required=True, default=fields.Date.today)
    date_to = fields.Date(string="Đến ngày", required=True, default=fields.Date.today)

    month = fields.Selection(
        [(str(i), f"Tháng {i}") for i in range(1, 13)],
        string="Tháng",
    )

    quarter = fields.Selection(
        [
            ("1", "Q1"),
            ("2", "Q2"),
            ("3", "Q3"),
            ("4", "Q4"),
        ],
        string="Quý",
    )

    year = fields.Integer(
        string="Năm",
        default=lambda self: fields.Date.today().year,
    )

    opening_bank = fields.Monetary(
        string="Tồn đầu kỳ - Ngân hàng",
        currency_field="currency_id",
        default=0.0,
    )

    opening_cash = fields.Monetary(
        string="Tồn đầu kỳ - Tiền mặt",
        currency_field="currency_id",
        default=0.0,
    )

    period_label = fields.Char(
        string="Kỳ báo cáo",
        compute="_compute_period_label",
        store=False,
    )

    # =========================================================
    # Basic helpers
    # =========================================================
    def _format_ddmmyyyy(self, d):
        if not d:
            return ""

        if isinstance(d, str):
            try:
                d = fields.Date.from_string(d)
            except Exception:
                return d

        return d.strftime("%d/%m/%Y")

    def _to_float(self, value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def _resolve_dates(self):
        self.ensure_one()

        today = fields.Date.context_today(self)

        if self.period_type == "custom":
            if not self.date_from or not self.date_to:
                raise UserError("Vui lòng chọn Từ ngày/Đến ngày.")
            return self.date_from, self.date_to

        y = int(self.year or today.year)

        if self.period_type == "month":
            m = int(self.month) if self.month else int(today.month)
            if m < 1 or m > 12:
                m = int(today.month)

            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, 1), date(y, m, last_day)

        if self.period_type == "quarter":
            q = int(self.quarter) if self.quarter else int((today.month - 1) // 3 + 1)
            if q < 1 or q > 4:
                q = int((today.month - 1) // 3 + 1)

            m1 = (q - 1) * 3 + 1
            m3 = m1 + 2
            last_day = calendar.monthrange(y, m3)[1]
            return date(y, m1, 1), date(y, m3, last_day)

        if self.period_type == "year":
            return date(y, 1, 1), date(y, 12, 31)

        return self.date_from, self.date_to

    def _domain_company_safe(self, model_name):
        Model = self.env[model_name]
        if "company_id" in Model._fields:
            return [("company_id", "=", self.company_id.id)]
        return []

    # =========================================================
    # Balance helpers
    # =========================================================
    def _get_opening_snapshot_record(self, date_from):
        self.ensure_one()

        return self.env["cash.daily.balance"].search(
            [
                ("company_id", "=", self.company_id.id),
                ("date", "<", date_from),
            ],
            order="date desc, id desc",
            limit=1,
        )

    def _get_opening_from_snapshot(self, date_from):
        self.ensure_one()

        prev = self._get_opening_snapshot_record(date_from)
        if prev:
            return prev.closing_bank, prev.closing_cash, True

        return 0.0, 0.0, False

    def _save_opening_snapshot(self, date_from):
        """
        Lưu tồn đầu kỳ nhập tay thành tồn cuối của ngày trước date_from.

        Ví dụ:
        date_from = 10/05/2026
        opening_bank = 100,000,000
        opening_cash = 20,000,000

        => lưu cash.daily.balance ngày 09/05/2026
        """
        self.ensure_one()

        opening_date = date_from - timedelta(days=1)

        Balance = self.env["cash.daily.balance"]

        snap = Balance.search(
            [
                ("company_id", "=", self.company_id.id),
                ("date", "=", opening_date),
            ],
            limit=1,
        )

        vals = {
            "company_id": self.company_id.id,
            "date": opening_date,
            "currency_id": self.currency_id.id,
            "closing_bank": self.opening_bank or 0.0,
            "closing_cash": self.opening_cash or 0.0,
        }

        if snap:
            snap.write(vals)
        else:
            Balance.create(vals)

    def _save_closing_snapshot(self, date_to, closing_bank, closing_cash):
        self.ensure_one()

        Balance = self.env["cash.daily.balance"]

        snap = Balance.search(
            [
                ("company_id", "=", self.company_id.id),
                ("date", "=", date_to),
            ],
            limit=1,
        )

        vals = {
            "company_id": self.company_id.id,
            "date": date_to,
            "currency_id": self.currency_id.id,
            "closing_bank": closing_bank,
            "closing_cash": closing_cash,
        }

        if snap:
            snap.write(vals)
        else:
            Balance.create(vals)

    def _apply_opening_logic(self, date_from, save_manual_opening=False):
        """
        Logic tồn đầu kỳ:

        1. Nếu đã có cash.daily.balance trước date_from:
           => lấy dòng gần nhất làm tồn đầu kỳ.

        2. Nếu chưa có:
           => dùng số user nhập tay trên OWL.

        3. Nếu save_manual_opening=True và chưa có snapshot:
           => lưu số nhập tay thành tồn cuối ngày trước date_from.
        """
        self.ensure_one()

        snapshot_bank, snapshot_cash, has_snapshot = self._get_opening_from_snapshot(date_from)

        if has_snapshot:
            self.opening_bank = snapshot_bank
            self.opening_cash = snapshot_cash
            return snapshot_bank, snapshot_cash, True

        manual_bank = self.opening_bank or 0.0
        manual_cash = self.opening_cash or 0.0

        self.opening_bank = manual_bank
        self.opening_cash = manual_cash

        if save_manual_opening and (manual_bank != 0.0 or manual_cash != 0.0):
            self._save_opening_snapshot(date_from)

        return manual_bank, manual_cash, False

    # =========================================================
    # Sum helpers
    # =========================================================
    def _sum_receipts(self, date_from, date_to):
        self.ensure_one()

        domain = [
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("state", "=", "posted"),
        ] + self._domain_company_safe("account.receipt")

        receipts = self.env["account.receipt"].search(
            domain,
            order="date asc, id asc",
        )

        bank = sum(receipts.filtered(lambda r: r.payment_method == "bank").mapped("amount"))
        cash = sum(receipts.filtered(lambda r: r.payment_method != "bank").mapped("amount"))

        return bank, cash, receipts

    def _sum_payments(self, date_from, date_to):
        self.ensure_one()

        domain = [
            ("date_payment", ">=", date_from),
            ("date_payment", "<=", date_to),
            ("state", "=", "done"),
        ] + self._domain_company_safe("account.payment.request")

        payments = self.env["account.payment.request"].search(
            domain,
            order="date_payment asc, id asc",
        )

        bank = sum(payments.filtered(lambda p: p.payment_type == "bank").mapped("total"))
        cash = sum(payments.filtered(lambda p: p.payment_type != "bank").mapped("total"))

        return bank, cash, payments

    def _get_project_text(self, payment):
        if not payment:
            return ""

        if payment.cost_classification == "project":
            parts = []

            if payment.expense_category_id:
                parts.append(payment.expense_category_id.name)

            if payment.project_id:
                parts.append(payment.project_id.name)

            return " - ".join(parts)

        if payment.expense_category_id:
            return payment.expense_category_id.name

        return ""

    # =========================================================
    # Title / label
    # =========================================================
    def _get_report_title(self):
        self.ensure_one()

        if self.period_type == "month":
            return f"Báo cáo thu chi Tháng {int(self.month or 1)} Năm {self.year}"

        if self.period_type == "quarter":
            return f"Báo cáo thu chi Quý {int(self.quarter or 1)} Năm {self.year}"

        if self.period_type == "year":
            return f"Báo cáo thu chi Năm {self.year}"

        date_from, date_to = self._resolve_dates()
        df_str = self._format_ddmmyyyy(date_from)
        dt_str = self._format_ddmmyyyy(date_to)

        if date_from == date_to:
            return f"Báo cáo thu chi ngày {df_str}"

        return f"Báo cáo thu chi từ {df_str} đến {dt_str}"

    @api.depends("period_type", "date_from", "date_to", "month", "quarter", "year")
    def _compute_period_label(self):
        for wizard in self:
            try:
                date_from, date_to = wizard._resolve_dates()
                df_str = wizard._format_ddmmyyyy(date_from)
                dt_str = wizard._format_ddmmyyyy(date_to)

                if wizard.period_type == "month":
                    wizard.period_label = f"Tháng {int(wizard.month or 1)} Năm {wizard.year}"
                elif wizard.period_type == "quarter":
                    wizard.period_label = f"Quý {int(wizard.quarter or 1)} Năm {wizard.year}"
                elif wizard.period_type == "year":
                    wizard.period_label = f"Năm {wizard.year}"
                else:
                    if date_from == date_to:
                        wizard.period_label = f"ngày {df_str}"
                    else:
                        wizard.period_label = f"từ {df_str} đến {dt_str}"
            except Exception:
                wizard.period_label = ""

    # =========================================================
    # Legacy onchange, giữ lại nếu còn dùng wizard cũ ở chỗ khác
    # =========================================================
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        df = res.get("date_from") or fields.Date.today()

        if isinstance(df, str):
            df = fields.Date.from_string(df)

        temp = self.new(
            {
                "company_id": self.env.company.id,
                "currency_id": self.env.company.currency_id.id,
                "date_from": df,
                "date_to": df,
                "period_type": "custom",
            }
        )

        bank, cash, has_snapshot = temp._get_opening_from_snapshot(df)

        if has_snapshot:
            res.setdefault("opening_bank", bank)
            res.setdefault("opening_cash", cash)

        return res

    @api.onchange("period_type")
    def _onchange_period_type_init_defaults(self):
        for wizard in self:
            today = fields.Date.context_today(wizard)

            if not wizard.year:
                wizard.year = today.year

            if wizard.period_type == "month" and not wizard.month:
                wizard.month = str(today.month)

            if wizard.period_type == "quarter" and not wizard.quarter:
                q = (today.month - 1) // 3 + 1
                wizard.quarter = str(q)

    @api.onchange("period_type", "month", "quarter", "year")
    def _onchange_period_pick(self):
        for wizard in self:
            if not wizard.period_type:
                continue

            if wizard.period_type == "custom":
                continue

            date_from, date_to = wizard._resolve_dates()
            wizard.date_from = date_from
            wizard.date_to = date_to

            bank, cash, has_snapshot = wizard._get_opening_from_snapshot(date_from)
            if has_snapshot:
                wizard.opening_bank = bank
                wizard.opening_cash = cash

    @api.onchange("date_from")
    def _onchange_suggest_opening(self):
        for wizard in self:
            if not wizard.date_from:
                continue

            bank, cash, has_snapshot = wizard._get_opening_from_snapshot(wizard.date_from)
            if has_snapshot:
                wizard.opening_bank = bank
                wizard.opening_cash = cash

    @api.constrains("date_from", "date_to")
    def _check_range(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise UserError("Ngày bắt đầu không được lớn hơn ngày kết thúc.")

    # =========================================================
    # Prepare data
    # =========================================================
    def _prepare_report_core(self, save_snapshot=False):
        self.ensure_one()

        date_from, date_to = self._resolve_dates()

        if date_from > date_to:
            raise UserError("Ngày bắt đầu không được lớn hơn ngày kết thúc.")

        opening_bank, opening_cash, has_opening_snapshot = self._apply_opening_logic(
            date_from,
            save_manual_opening=save_snapshot,
        )

        receipt_bank, receipt_cash, receipts = self._sum_receipts(date_from, date_to)
        payment_bank, payment_cash, payments = self._sum_payments(date_from, date_to)

        closing_bank = opening_bank + receipt_bank - payment_bank
        closing_cash = opening_cash + receipt_cash - payment_cash

        if save_snapshot:
            self._save_closing_snapshot(date_to, closing_bank, closing_cash)

        receipts = receipts.sorted(
            key=lambda r: (
                r.payment_method != "bank",
                r.date or date.min,
                r.id,
            )
        )

        payments = payments.sorted(
            key=lambda p: (
                p.payment_type != "bank",
                p.date_payment or date.min,
                p.id,
            )
        )

        return {
            "date_from": date_from,
            "date_to": date_to,
            "date_from_label": self._format_ddmmyyyy(date_from),
            "date_to_label": self._format_ddmmyyyy(date_to),

            "opening_bank": opening_bank,
            "opening_cash": opening_cash,
            "has_opening_snapshot": has_opening_snapshot,

            "receipt_bank": receipt_bank,
            "receipt_cash": receipt_cash,
            "payment_bank": payment_bank,
            "payment_cash": payment_cash,

            "closing_bank": closing_bank,
            "closing_cash": closing_cash,

            "receipts": receipts,
            "payments": payments,
        }

    def _prepare_qweb_data(self, save_snapshot=False):
        self.ensure_one()

        core = self._prepare_report_core(save_snapshot=save_snapshot)

        return {
            "doc_ids": self.ids,
            "period_label": self.period_label or self._get_report_title(),
            "date_from": core["date_from_label"],
            "date_to": core["date_to_label"],

            "account_receipt_ids": core["receipts"].ids,
            "account_payment_ids": core["payments"].ids,

            "opening_bank": core["opening_bank"],
            "opening_cash": core["opening_cash"],

            "sum_receipt_bank": core["receipt_bank"],
            "sum_receipt_cash": core["receipt_cash"],
            "sum_payment_bank": core["payment_bank"],
            "sum_payment_cash": core["payment_cash"],

            "closing_bank": core["closing_bank"],
            "closing_cash": core["closing_cash"],

            "currency_id": self.currency_id.id,
        }

    def _prepare_owl_data(self, save_snapshot=False):
        self.ensure_one()

        core = self._prepare_report_core(save_snapshot=save_snapshot)

        receipts = core["receipts"]
        payments = core["payments"]

        rows = []
        max_len = max(len(receipts), len(payments))

        for i in range(max_len):
            receipt = receipts[i] if i < len(receipts) else False
            payment = payments[i] if i < len(payments) else False

            rows.append(
                {
                    "index": i + 1,

                    "receipt_id": receipt.id if receipt else False,
                    "receipt_date": self._format_ddmmyyyy(receipt.date) if receipt else "",
                    "receipt_note": receipt.note or "" if receipt else "",
                    "receipt_bank": receipt.amount if receipt and receipt.payment_method == "bank" else 0.0,
                    "receipt_cash": receipt.amount if receipt and receipt.payment_method != "bank" else 0.0,

                    "payment_id": payment.id if payment else False,
                    "payment_date": self._format_ddmmyyyy(payment.date_payment) if payment else "",
                    "payment_note": payment.note or "" if payment else "",
                    "payment_bank": payment.total if payment and payment.payment_type == "bank" else 0.0,
                    "payment_cash": payment.total if payment and payment.payment_type != "bank" else 0.0,
                    "project_text": self._get_project_text(payment) if payment else "",
                }
            )

        return {
            "title": self._get_report_title(),
            "period_label": self.period_label or "",

            "date_from": fields.Date.to_string(core["date_from"]),
            "date_to": fields.Date.to_string(core["date_to"]),
            "date_from_label": core["date_from_label"],
            "date_to_label": core["date_to_label"],

            "currency": {
                "id": self.currency_id.id,
                "symbol": self.currency_id.symbol or "",
                "position": self.currency_id.position or "after",
            },

            "opening_bank": core["opening_bank"],
            "opening_cash": core["opening_cash"],
            "has_opening_snapshot": core["has_opening_snapshot"],

            "sum_receipt_bank": core["receipt_bank"],
            "sum_receipt_cash": core["receipt_cash"],
            "sum_payment_bank": core["payment_bank"],
            "sum_payment_cash": core["payment_cash"],

            "closing_bank": core["closing_bank"],
            "closing_cash": core["closing_cash"],

            "rows": rows,
        }

    # =========================================================
    # OWL filters
    # =========================================================
    def _vals_from_filters(self, filters):
        filters = filters or {}

        today = fields.Date.context_today(self)

        period_type = filters.get("period_type") or "custom"

        vals = {
            "company_id": self.env.company.id,
            "currency_id": self.env.company.currency_id.id,
            "period_type": period_type,

            "date_from": filters.get("date_from") or today,
            "date_to": filters.get("date_to") or today,

            "month": str(filters.get("month") or today.month),
            "quarter": str(filters.get("quarter") or ((today.month - 1) // 3 + 1)),
            "year": int(filters.get("year") or today.year),

            "opening_bank": self._to_float(filters.get("opening_bank")),
            "opening_cash": self._to_float(filters.get("opening_cash")),
        }

        return vals

    @api.model
    def get_opening_from_filters(self, filters=None):
        """
        Dùng khi user đổi ngày/tháng/quý/năm trên OWL.
        Trả về tồn đầu kỳ đúng theo snapshot trước date_from.

        Nếu chưa có snapshot thì trả về 0 để user nhập tay,
        tránh giữ nhầm số tồn của kỳ cũ.
        """
        wizard = self.create(self._vals_from_filters(filters))

        date_from, date_to = wizard._resolve_dates()

        bank, cash, has_snapshot = wizard._get_opening_from_snapshot(date_from)

        return {
            "date_from": fields.Date.to_string(date_from),
            "date_to": fields.Date.to_string(date_to),
            "date_from_label": wizard._format_ddmmyyyy(date_from),
            "date_to_label": wizard._format_ddmmyyyy(date_to),

            "opening_bank": bank if has_snapshot else 0.0,
            "opening_cash": cash if has_snapshot else 0.0,
            "has_snapshot": has_snapshot,
        }

    @api.model
    def get_report_data(self, filters=None):
        wizard = self.create(self._vals_from_filters(filters))

        # save_snapshot=True để nếu user nhập tồn đầu kỳ tay,
        # hệ thống lưu lại thành cash.daily.balance ngày trước kỳ.
        return wizard._prepare_owl_data(save_snapshot=True)

    @api.model
    def action_export_pdf_from_filters(self, filters=None):
        wizard = self.create(self._vals_from_filters(filters))
        data = wizard._prepare_qweb_data(save_snapshot=True)
        return self.env.ref("report_daily_cash_flow.daily_cash_flow_report").report_action(wizard, data=data)

    @api.model
    def action_export_excel_from_filters(self, filters=None):
        wizard = self.create(self._vals_from_filters(filters))
        return wizard.action_export_excel()

    # =========================================================
    # Old wizard actions
    # =========================================================
    def action_generate_report(self):
        self.ensure_one()
        data = self._prepare_qweb_data(save_snapshot=True)
        return self.env.ref("report_daily_cash_flow.daily_cash_flow_report").report_action(self, data=data)

    def action_export_excel(self):
        self.ensure_one()

        core = self._prepare_report_core(save_snapshot=True)

        date_from = core["date_from"]
        date_to = core["date_to"]

        opening_date = date_from - timedelta(days=1)
        opening_date_str = opening_date.strftime("%d/%m/%Y")
        closing_date_str = date_to.strftime("%d/%m/%Y")

        receipts = core["receipts"]
        payments = core["payments"]

        opening_bank = core["opening_bank"]
        opening_cash = core["opening_cash"]

        receipt_bank = core["receipt_bank"]
        receipt_cash = core["receipt_cash"]
        payment_bank = core["payment_bank"]
        payment_cash = core["payment_cash"]

        closing_bank = core["closing_bank"]
        closing_cash = core["closing_cash"]

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Báo cáo thu chi")

        fmt_title = workbook.add_format(
            {
                "bold": True,
                "font_size": 16,
                "align": "center",
                "valign": "vcenter",
            }
        )

        fmt_group_thu = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#92D050",
            }
        )

        fmt_group_chi = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#FFF2CC",
            }
        )

        fmt_head_thu = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#92D050",
            }
        )

        fmt_head_chi = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#FFF2CC",
            }
        )

        fmt_head_stt = workbook.add_format(
            {
                "bold": True,
                "border": 1,
                "align": "center",
                "valign": "vcenter",
                "bg_color": "#D9E1F2",
            }
        )

        fmt_text = workbook.add_format(
            {
                "border": 1,
                "valign": "top",
                "align": "left",
                "text_wrap": True,
            }
        )

        fmt_center = workbook.add_format(
            {
                "border": 1,
                "align": "center",
                "valign": "vcenter",
            }
        )

        fmt_money = workbook.add_format(
            {
                "border": 1,
                "num_format": "#,##0",
                "align": "right",
                "valign": "vcenter",
            }
        )

        fmt_money_bold = workbook.add_format(
            {
                "border": 1,
                "num_format": "#,##0",
                "bold": True,
                "align": "right",
                "valign": "vcenter",
            }
        )

        fmt_center_bold = workbook.add_format(
            {
                "border": 1,
                "bold": True,
                "align": "center",
                "valign": "vcenter",
                "text_wrap": True,
            }
        )

        sheet.set_column("A:A", 6)
        sheet.set_column("B:B", 13)
        sheet.set_column("C:C", 34)
        sheet.set_column("D:E", 16)
        sheet.set_column("F:F", 13)
        sheet.set_column("G:G", 34)
        sheet.set_column("H:I", 16)
        sheet.set_column("J:J", 45)

        report_title = self._get_report_title()
        sheet.merge_range("A1:J1", report_title.upper(), fmt_title)

        row = 3

        sheet.write(row, 0, "", fmt_head_stt)
        sheet.merge_range(row, 1, row, 4, "THU TIỀN", fmt_group_thu)
        sheet.merge_range(row, 5, row, 9, "CHI TIỀN", fmt_group_chi)
        row += 1

        sheet.write(row, 0, "STT", fmt_head_stt)

        sheet.write(row, 1, "Ngày", fmt_head_thu)
        sheet.write(row, 2, "Nội dung thu", fmt_head_thu)
        sheet.write(row, 3, "Ngân hàng", fmt_head_thu)
        sheet.write(row, 4, "Tiền mặt", fmt_head_thu)

        sheet.write(row, 5, "Ngày", fmt_head_chi)
        sheet.write(row, 6, "Nội dung chi", fmt_head_chi)
        sheet.write(row, 7, "Ngân hàng", fmt_head_chi)
        sheet.write(row, 8, "Tiền mặt", fmt_head_chi)
        sheet.write(row, 9, "Gói thầu / Công trình / Địa điểm / Chủ đầu tư", fmt_head_chi)
        row += 1

        sheet.write(row, 0, "", fmt_text)
        sheet.write(row, 1, "", fmt_center)
        sheet.write(row, 2, f"TỒN ĐẦU KỲ\n({opening_date_str})", fmt_center_bold)
        sheet.write(row, 3, opening_bank, fmt_money_bold)
        sheet.write(row, 4, opening_cash, fmt_money_bold)
        sheet.write_row(row, 5, ["", "", "", "", ""], fmt_text)
        sheet.set_row(row, 34)
        row += 1

        max_len = max(len(receipts), len(payments))

        for i in range(max_len):
            sheet.write(row, 0, i + 1, fmt_center)

            if i < len(receipts):
                receipt = receipts[i]
                sheet.write(row, 1, self._format_ddmmyyyy(receipt.date), fmt_center)
                sheet.write(row, 2, receipt.note or "", fmt_text)

                if receipt.payment_method == "bank":
                    sheet.write(row, 3, receipt.amount or 0.0, fmt_money)
                    sheet.write(row, 4, "", fmt_text)
                else:
                    sheet.write(row, 3, "", fmt_text)
                    sheet.write(row, 4, receipt.amount or 0.0, fmt_money)
            else:
                sheet.write_row(row, 1, ["", "", "", ""], fmt_text)

            if i < len(payments):
                payment = payments[i]
                sheet.write(row, 5, self._format_ddmmyyyy(payment.date_payment), fmt_center)
                sheet.write(row, 6, payment.note or "", fmt_text)

                if payment.payment_type == "bank":
                    sheet.write(row, 7, payment.total or 0.0, fmt_money)
                    sheet.write(row, 8, "", fmt_text)
                else:
                    sheet.write(row, 7, "", fmt_text)
                    sheet.write(row, 8, payment.total or 0.0, fmt_money)

                sheet.write(row, 9, self._get_project_text(payment), fmt_text)
            else:
                sheet.write_row(row, 5, ["", "", "", "", ""], fmt_text)

            sheet.set_row(row, 32)
            row += 1

        sheet.write(row, 0, "", fmt_text)
        sheet.write(row, 1, "", fmt_text)
        sheet.write(row, 2, "TỔNG THU / CHI", fmt_center_bold)
        sheet.write(row, 3, receipt_bank, fmt_money_bold)
        sheet.write(row, 4, receipt_cash, fmt_money_bold)
        sheet.write(row, 5, "", fmt_text)
        sheet.write(row, 6, "", fmt_text)
        sheet.write(row, 7, payment_bank, fmt_money_bold)
        sheet.write(row, 8, payment_cash, fmt_money_bold)
        sheet.write(row, 9, "", fmt_text)
        sheet.set_row(row, 30)
        row += 1

        sheet.write(row, 0, "", fmt_text)
        sheet.write(row, 1, "", fmt_text)
        sheet.write(row, 2, f"TỒN CUỐI KỲ\n({closing_date_str})", fmt_center_bold)
        sheet.write(row, 3, closing_bank, fmt_money_bold)
        sheet.write(row, 4, closing_cash, fmt_money_bold)
        sheet.write_row(row, 5, ["", "", "", "", ""], fmt_text)
        sheet.set_row(row, 34)

        sheet.freeze_panes(5, 0)

        workbook.close()
        output.seek(0)

        safe_name = report_title.replace(" ", "_").replace("/", "-")

        attachment = self.env["ir.attachment"].create(
            {
                "name": f"{safe_name}.xlsx",
                "type": "binary",
                "datas": base64.b64encode(output.read()),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
        )

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }