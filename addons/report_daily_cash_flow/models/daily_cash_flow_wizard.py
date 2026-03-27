# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import date
import calendar
import io
import base64
from odoo.tools.misc import xlsxwriter
from datetime import timedelta


class DailyCashFlowWizard(models.TransientModel):
    _name = "daily.cash.flow.wizard"
    _description = "Cash Flow Report Wizard (By Period)"

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

    # ---- chọn kỳ ----
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

    month = fields.Selection([(str(i), f"Tháng {i}") for i in range(1, 13)], string="Tháng")
    quarter = fields.Selection([("1", "Q1"), ("2", "Q2"), ("3", "Q3"), ("4", "Q4")], string="Quý")
    year = fields.Integer(string="Năm", default=lambda self: fields.Date.today().year)

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

    period_label = fields.Char(string="Kỳ báo cáo", compute="_compute_period_label", store=False)

    # -------------------------
    # Helpers
    # -------------------------
    def _format_ddmmyyyy(self, d):
        if not d:
            return ""
        if isinstance(d, str):
            return d
        return d.strftime("%d/%m/%Y")

    def _resolve_dates(self):
        """Trả về (date_from, date_to) đã được chuẩn hoá theo period_type.
        Không được crash dù month/quarter đang rỗng (onchange).
        """
        self.ensure_one()
        today = fields.Date.context_today(self)

        if self.period_type == "custom":
            if not self.date_from or not self.date_to:
                raise UserError("Vui lòng chọn Từ ngày/Đến ngày.")
            return self.date_from, self.date_to

        y = int(self.year or today.year)

        if self.period_type == "month":
            # month có thể False khi vừa chọn period_type
            m = int(self.month) if self.month else int(today.month)
            if m < 1 or m > 12:
                m = int(today.month)
            last = calendar.monthrange(y, m)[1]
            return date(y, m, 1), date(y, m, last)

        if self.period_type == "quarter":
            # quarter có thể False khi vừa chọn period_type
            q = int(self.quarter) if self.quarter else int((today.month - 1) // 3 + 1)
            if q < 1 or q > 4:
                q = int((today.month - 1) // 3 + 1)
            m1 = (q - 1) * 3 + 1
            m3 = m1 + 2
            last = calendar.monthrange(y, m3)[1]
            return date(y, m1, 1), date(y, m3, last)

        if self.period_type == "year":
            return date(y, 1, 1), date(y, 12, 31)

        return self.date_from, self.date_to

    def _domain_company_safe(self, model_name):
        """Chỉ add company_id nếu model có field đó."""
        Model = self.env[model_name]
        if "company_id" in Model._fields:
            return [("company_id", "=", self.company_id.id)]
        return []

    def _get_opening_from_snapshot(self, date_from):
        """Tồn đầu kỳ = snapshot gần nhất có date < date_from."""
        Balance = self.env["cash.daily.balance"]
        prev = Balance.search(
            [
                ("company_id", "=", self.company_id.id),
                ("date", "<", date_from),
            ],
            order="date desc, id desc",
            limit=1,
        )
        if prev:
            return prev.closing_bank, prev.closing_cash
        return 0.0, 0.0

    def _sum_receipts(self, date_from, date_to):
        """Tổng THU theo kênh trong khoảng ngày."""
        dom = [
            ("date", ">=", date_from),
            ("date", "<=", date_to),
            ("state", "=", "posted"),
        ] + self._domain_company_safe("account.receipt")

        receipts = self.env["account.receipt"].search(dom)
        bank = sum(r.amount for r in receipts.filtered(lambda r: r.payment_method == "bank"))
        cash = sum(r.amount for r in receipts.filtered(lambda r: r.payment_method != "bank"))
        return bank, cash, receipts

    def _sum_payments(self, date_from, date_to):
        """Tổng CHI theo kênh trong khoảng ngày."""
        dom = [
            ("date_payment", ">=", date_from),
            ("date_payment", "<=", date_to),
            ("state", "=", "done"),
        ] + self._domain_company_safe("account.payment.request")

        pays = self.env["account.payment.request"].search(dom)
        bank = sum(p.total for p in pays.filtered(lambda p: p.payment_type == "bank"))
        cash = sum(p.total for p in pays.filtered(lambda p: p.payment_type != "bank"))
        return bank, cash, pays

    # -------------------------
    # Defaults / onchange
    # -------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        df = res.get("date_from") or fields.Date.today()
        dt = res.get("date_to") or fields.Date.today()
        if df > dt:
            df, dt = dt, df

        prev = self.env["cash.daily.balance"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("date", "<", df),
            ],
            order="date desc, id desc",
            limit=1,
        )
        if prev:
            res.setdefault("opening_bank", prev.closing_bank)
            res.setdefault("opening_cash", prev.closing_cash)

        return res

    @api.onchange("period_type")
    def _onchange_period_type_init_defaults(self):
        """Vừa đổi period_type thì set default month/quarter/year để _resolve_dates không bị month=0."""
        for w in self:
            today = fields.Date.context_today(w)
            if not w.year:
                w.year = today.year

            if w.period_type == "month":
                if not w.month:
                    w.month = str(today.month)

            elif w.period_type == "quarter":
                if not w.quarter:
                    q = (today.month - 1) // 3 + 1
                    w.quarter = str(q)

    @api.onchange("period_type", "month", "quarter", "year")
    def _onchange_period_pick(self):
        """Nếu chọn month/quarter/year thì auto set date_from/date_to."""
        for w in self:
            if not w.period_type:
                continue
            if w.period_type == "custom":
                continue

            df, dt = w._resolve_dates()
            w.date_from = df
            w.date_to = dt

    @api.onchange("date_from")
    def _onchange_suggest_opening(self):
        for w in self:
            if not w.date_from:
                continue
            bank, cash = w._get_opening_from_snapshot(w.date_from)
            if bank or cash:
                w.opening_bank = bank
                w.opening_cash = cash

    @api.constrains("date_from", "date_to")
    def _check_range(self):
        for w in self:
            if w.date_from and w.date_to and w.date_from > w.date_to:
                raise UserError("Ngày bắt đầu không được lớn hơn ngày kết thúc.")

    @api.depends("period_type", "date_from", "date_to", "month", "quarter", "year")
    def _compute_period_label(self):
        for w in self:
            try:
                df, dt = w._resolve_dates()
                df_str = w._format_ddmmyyyy(df)
                dt_str = w._format_ddmmyyyy(dt)

                if w.period_type == "month":
                    w.period_label = f"Tháng {int(w.month)} Năm {w.year}"
                elif w.period_type == "quarter":
                    w.period_label = f"Quý {int(w.quarter)} Năm {w.year}"
                elif w.period_type == "year":
                    w.period_label = f"Năm {w.year}"
                else:
                    # custom
                    if df == dt:
                        w.period_label = f"ngày {df_str}"
                    else:
                        w.period_label = f"từ {df_str} đến {dt_str}"
            except Exception:
                w.period_label = ""

    # -------------------------
    # Action
    # -------------------------
    def action_generate_report(self):
        self.ensure_one()

        date_from, date_to = self._resolve_dates()
        if date_from > date_to:
            raise UserError("Khoảng ngày không hợp lệ.")

        # Nếu user không nhập opening (0/0) mà có snapshot thì gợi ý (không ép)
        if (self.opening_bank or 0.0) == 0.0 and (self.opening_cash or 0.0) == 0.0:
            ob, oc = self._get_opening_from_snapshot(date_from)
            if ob or oc:
                self.opening_bank = ob
                self.opening_cash = oc

        # Thu/Chi + danh sách detail trong kỳ
        r_bank, r_cash, receipts = self._sum_receipts(date_from, date_to)
        p_bank, p_cash, payments = self._sum_payments(date_from, date_to)

        # Tồn cuối kỳ
        closing_bank = (self.opening_bank or 0.0) + r_bank - p_bank
        closing_cash = (self.opening_cash or 0.0) + r_cash - p_cash

        # Lưu snapshot tại date_to (tồn cuối kỳ)
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

        data = {
            "doc_ids": self.ids,
            "period_label": self.period_label,
            "date_from": self._format_ddmmyyyy(date_from),
            "date_to": self._format_ddmmyyyy(date_to),

            "account_receipt_ids": receipts.ids,
            "account_payment_ids": payments.ids,

            "opening_bank": self.opening_bank or 0.0,
            "opening_cash": self.opening_cash or 0.0,

            "sum_receipt_bank": r_bank,
            "sum_receipt_cash": r_cash,
            "sum_payment_bank": p_bank,
            "sum_payment_cash": p_cash,

            "closing_bank": closing_bank,
            "closing_cash": closing_cash,

            "currency_id": self.currency_id.id,
        }

        return self.env.ref("report_daily_cash_flow.daily_cash_flow_report").report_action(self, data=data)
    def _get_report_title(self):
        """Trả về title + filename theo filter"""
        self.ensure_one()

        if self.period_type == "month":
            return f"Báo cáo thu chi Tháng {int(self.month)} Năm {self.year}"

        if self.period_type == "quarter":
            return f"Báo cáo thu chi Quý {int(self.quarter)} Năm {self.year}"

        if self.period_type == "year":
            return f"Báo cáo thu chi Năm {self.year}"

        # custom range
        df, dt = self._resolve_dates()
        df_str = self._format_ddmmyyyy(df)
        dt_str = self._format_ddmmyyyy(dt)

        if df == dt:
            return f"Báo cáo thu chi ngày {df_str}"
        return f"Báo cáo thu chi từ {df_str} đến {dt_str}"
    def action_export_excel(self):
        self.ensure_one()

        date_from, date_to = self._resolve_dates()
        opening_date = date_from - timedelta(days=1)
        closing_date = date_to

        opening_date_str = opening_date.strftime("%d/%m/%Y")
        closing_date_str = closing_date.strftime("%d/%m/%Y")

        # Thu / Chi
        r_bank, r_cash, receipts = self._sum_receipts(date_from, date_to)
        p_bank, p_cash, payments = self._sum_payments(date_from, date_to)

        opening_bank = self.opening_bank or 0.0
        opening_cash = self.opening_cash or 0.0

        closing_bank = opening_bank + r_bank - p_bank
        closing_cash = opening_cash + r_cash - p_cash

        # -------------------------
        # Tạo file Excel
        # -------------------------
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet("Báo cáo thu chi")

        # ===== FORMAT =====
        fmt_title = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center',
            'valign': 'vcenter'
        })

        fmt_group_thu = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#92D050'
        })

        fmt_group_chi = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#FFF2CC'
        })

        fmt_head_thu = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'bg_color': '#92D050'
        })

        fmt_head_chi = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'bg_color': '#FFF2CC'
        })

        fmt_head_stt = workbook.add_format({
            'bold': True,
            'border': 1,
            'align': 'center',
            'bg_color': '#D9E1F2'
        })

        # 🔥 FORMAT TEXT CÓ WRAP (QUAN TRỌNG)
        fmt_text = workbook.add_format({
            'border': 1,
            'valign': 'top',
            'align': 'left',
            'text_wrap': True
        })

        fmt_money = workbook.add_format({
            'border': 1,
            'num_format': '#,##0',
            'align': 'right',
            'valign': 'vcenter'
        })

        fmt_money_bold = workbook.add_format({
            'border': 1,
            'num_format': '#,##0',
            'bold': True,
            'align': 'right',
            'valign': 'vcenter'
        })

        fmt_center_bold = workbook.add_format({
            'border': 1,
            'bold': True,
            'align': 'center',
            'valign': 'vcenter'
        })

        # ===== COLUMN WIDTH =====
        sheet.set_column("A:A", 5)
        sheet.set_column("B:B", 38)
        sheet.set_column("C:D", 16)
        sheet.set_column("E:E", 38)
        sheet.set_column("F:G", 16)
        sheet.set_column("H:H", 48)

        # ===== TITLE =====
        report_title = self._get_report_title()
        sheet.merge_range("A1:H1", report_title.upper(), fmt_title)

        row = 3

        # ===== HEADER GROUP =====
        sheet.write(row, 0, "", fmt_head_stt)
        sheet.merge_range(row, 1, row, 3, "THU TIỀN", fmt_group_thu)
        sheet.merge_range(row, 4, row, 7, "CHI TIỀN", fmt_group_chi)
        row += 1

        # ===== HEADER DETAIL =====
        sheet.write(row, 0, "STT", fmt_head_stt)

        sheet.write(row, 1, "Nội dung thu", fmt_head_thu)
        sheet.write(row, 2, "Ngân hàng", fmt_head_thu)
        sheet.write(row, 3, "Tiền mặt", fmt_head_thu)

        sheet.write(row, 4, "Nội dung chi", fmt_head_chi)
        sheet.write(row, 5, "Ngân hàng", fmt_head_chi)
        sheet.write(row, 6, "Tiền mặt", fmt_head_chi)
        sheet.write(
            row, 7,
            "GÓI THẦU / CÔNG TRÌNH / ĐỊA ĐIỂM / CHỦ ĐẦU TƯ",
            fmt_head_chi
        )
        row += 1

        # ===== TỒN ĐẦU KỲ =====
        sheet.write(row, 0, "", fmt_text)
        sheet.write(
            row, 1,
            f"TỒN ĐẦU KỲ\n({opening_date_str})",
            fmt_center_bold
        )
        sheet.write(row, 2, opening_bank, fmt_money_bold)
        sheet.write(row, 3, opening_cash, fmt_money_bold)
        sheet.write_row(row, 4, ["", "", "", ""], fmt_text)
        sheet.set_row(row, 30)
        row += 1

        # ===== DATA =====
        max_len = max(len(receipts), len(payments))

        for i in range(max_len):
            sheet.write(row, 0, i + 1, fmt_text)

            # ---- THU ----
            if i < len(receipts):
                r = receipts[i]
                sheet.write(row, 1, r.note or "", fmt_text)
                if r.payment_method == "bank":
                    sheet.write(row, 2, r.amount, fmt_money)
                    sheet.write(row, 3, "", fmt_text)
                else:
                    sheet.write(row, 2, "", fmt_text)
                    sheet.write(row, 3, r.amount, fmt_money)
            else:
                sheet.write_row(row, 1, ["", "", ""], fmt_text)

            # ---- CHI ----
            if i < len(payments):
                p = payments[i]
                sheet.write(row, 4, p.note or "", fmt_text)
                if p.payment_type == "bank":
                    sheet.write(row, 5, p.total, fmt_money)
                    sheet.write(row, 6, "", fmt_text)
                else:
                    sheet.write(row, 5, "", fmt_text)
                    sheet.write(row, 6, p.total, fmt_money)

                project_text = ""
                if p.cost_classification == "project":
                    if p.expense_category_id:
                        project_text += p.expense_category_id.name + " - "
                    if p.project_id:
                        project_text += p.project_id.name
                elif p.expense_category_id:
                    project_text = p.expense_category_id.name

                sheet.write(row, 7, project_text, fmt_text)
            else:
                sheet.write_row(row, 4, ["", "", "", ""], fmt_text)

            sheet.set_row(row, 32)
            row += 1

        # ===== TỔNG =====
        sheet.write(row, 0, "", fmt_text)
        sheet.write(row, 1, "TỔNG THU / CHI", fmt_center_bold)
        sheet.write(row, 2, r_bank, fmt_money_bold)
        sheet.write(row, 3, r_cash, fmt_money_bold)
        sheet.write(row, 4, "", fmt_text)
        sheet.write(row, 5, p_bank, fmt_money_bold)
        sheet.write(row, 6, p_cash, fmt_money_bold)
        sheet.write(row, 7, "", fmt_text)
        sheet.set_row(row, 30)
        row += 1

        # ===== TỒN CUỐI =====
        sheet.write(row, 0, "", fmt_text)
        sheet.write(
            row, 1,
            f"TỒN CUỐI KỲ\n( {closing_date_str})",
            fmt_center_bold
        )
        sheet.write(row, 2, closing_bank, fmt_money_bold)
        sheet.write(row, 3, closing_cash, fmt_money_bold)
        sheet.write_row(row, 4, ["", "", "", ""], fmt_text)
        sheet.set_row(row, 30)

        # Freeze header (2 dòng header)
        sheet.freeze_panes(6, 0)

        workbook.close()
        output.seek(0)

        # -------------------------
        # Download
        # -------------------------
        safe_name = report_title.replace(" ", "_").replace("/", "-")
        attachment = self.env["ir.attachment"].create({
            "name": f"{safe_name}.xlsx",
            "type": "binary",
            "datas": base64.b64encode(output.read()),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        })

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content/{attachment.id}?download=true",
            "target": "self",
        }

