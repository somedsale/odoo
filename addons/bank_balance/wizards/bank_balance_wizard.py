# -*- coding: utf-8 -*-
from datetime import timedelta
from odoo import models, fields, api
from odoo.exceptions import UserError


class BankBalanceWizard(models.TransientModel):
    _name = "bank.balance.wizard"
    _description = "Wizard - Bank Balance (By Day / Multi Banks)"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    date = fields.Date(string="Ngày", required=True, default=fields.Date.context_today)

    line_ids = fields.One2many("bank.balance.wizard.line", "wizard_id", string="Ngân hàng")

    # -------------------------
    # helpers (safe company filter)
    # -------------------------
    def _model_has_field(self, model_name, field_name):
        return model_name in self.env and field_name in self.env[model_name]._fields

    def _domain_company_safe(self, model_name, company_id):
        if self._model_has_field(model_name, "company_id"):
            return [("company_id", "=", company_id)]
        return []

    def _get_prev_day_closing(self, company_id, bank_id, date_):
        prev = self.env["bank.daily.balance"].search(
            [
                ("company_id", "=", company_id),
                ("bank_id", "=", bank_id),
                ("date", "<", date_),
            ],
            order="date desc, id desc",
            limit=1,
        )
        return prev.closing_balance if prev else None

    def _get_day_snapshot(self, company_id, bank_id, date_):
        return self.env["bank.daily.balance"].search(
            [
                ("company_id", "=", company_id),
                ("bank_id", "=", bank_id),
                ("date", "=", date_),
            ],
            limit=1,
        )

    def _get_end_date_for_chain(self, company_id, bank_id, from_date):
        """
        Recompute từ ngày đang xem -> tới ngày cuối cùng đã từng có snapshot (nếu có),
        để “đẩy” lại tồn các ngày sau khi phát sinh chứng từ mới.
        """
        last = self.env["bank.daily.balance"].search(
            [
                ("company_id", "=", company_id),
                ("bank_id", "=", bank_id),
                ("date", ">=", from_date),
            ],
            order="date desc, id desc",
            limit=1,
        )
        return last.date if last else from_date

    def _upsert_snapshot(self, company_id, bank_id, date_, opening, closing):
        snap = self._get_day_snapshot(company_id, bank_id, date_)
        vals = {
            "company_id": company_id,
            "bank_id": bank_id,
            "date": date_,
            "currency_id": self.currency_id.id,
            "opening_balance": opening,
            "closing_balance": closing,
        }
        if snap:
            snap.write({"opening_balance": opening, "closing_balance": closing})
        else:
            self.env["bank.daily.balance"].create(vals)

    # -------------------------
    # sum receipts/payments (theo bank_id)
    # -------------------------
    def _sum_receipts(self, company_id, bank_id, date_):
        Model = "account.receipt"
        if Model not in self.env or not self._model_has_field(Model, "bank_id"):
            return 0.0

        dom = [("bank_id", "=", bank_id), ("date", "=", date_)] + self._domain_company_safe(Model, company_id)
        if self._model_has_field(Model, "state"):
            dom += [("state", "=", "posted")]

        rs = self.env[Model].search(dom)
        if not self._model_has_field(Model, "amount"):
            raise UserError("account.receipt thiếu field amount.")
        return sum(rs.mapped("amount")) or 0.0

    def _sum_payments(self, company_id, bank_id, date_):
        Model = "account.payment.request"
        if Model not in self.env or not self._model_has_field(Model, "bank_id"):
            return 0.0

        dom = [("bank_id", "=", bank_id), ("date_payment", "=", date_)] + self._domain_company_safe(Model, company_id)
        if self._model_has_field(Model, "state"):
            dom += [("state", "=", "done")]

        rs = self.env[Model].search(dom)
        # bạn dùng total (như cash flow), fallback amount_total nếu không có
        if self._model_has_field(Model, "total"):
            return sum(rs.mapped("total")) or 0.0
        if self._model_has_field(Model, "amount_total"):
            return sum(rs.mapped("amount_total")) or 0.0
        raise UserError("account.payment.request thiếu field total/amount_total.")

    # -------------------------
    # build lines
    # -------------------------
    def _collect_bank_ids(self, company_id, date_):
        bank_ids = set()

        # 1) banks đã từng có snapshot
        snaps = self.env["bank.daily.balance"].search([("company_id", "=", company_id)])
        bank_ids.update(snaps.mapped("bank_id").ids)

        # 2) banks phát sinh chứng từ đúng ngày đang xem
        if "account.receipt" in self.env and self._model_has_field("account.receipt", "bank_id"):
            rdom = [("date", "=", date_)] + self._domain_company_safe("account.receipt", company_id)
            if self._model_has_field("account.receipt", "state"):
                rdom += [("state", "=", "posted")]
            bank_ids.update(self.env["account.receipt"].search(rdom).mapped("bank_id").ids)

        if "account.payment.request" in self.env and self._model_has_field("account.payment.request", "bank_id"):
            pdom = [("date_payment", "=", date_)] + self._domain_company_safe("account.payment.request", company_id)
            if self._model_has_field("account.payment.request", "state"):
                pdom += [("state", "=", "done")]
            bank_ids.update(self.env["account.payment.request"].search(pdom).mapped("bank_id").ids)

        return [bid for bid in bank_ids if bid]

    def _rebuild_lines(self):
        self.ensure_one()
        if not self.date:
            self.line_ids = [(5, 0, 0)]
            return

        bank_ids = self._collect_bank_ids(self.company_id.id, self.date)

        # KHÔNG unlink / write trong onchange -> dùng commands
        cmds = [(5, 0, 0)]  # clear
        cmds += [(0, 0, {"bank_id": bid}) for bid in bank_ids]
        self.line_ids = cmds

        # calc ngay trên record in-memory
        for l in self.line_ids:
            self._recalc_one_line(l)

    def _cleanup_empty_lines(self):
        """Tránh lỗi khi user bấm nút mà đang có 1 dòng mới chưa chọn bank."""
        empty = self.line_ids.filtered(lambda l: not l.bank_id)
        if empty:
            empty.unlink()

    def _recalc_one_line(self, line):
        if not line.bank_id or not self.date:
            return

        company_id = self.company_id.id
        bank_id = line.bank_id.id
        date_ = self.date

        prev_closing = self._get_prev_day_closing(company_id, bank_id, date_)

        # snapshot của chính ngày đó (để mở lại ngày đầu tiên vẫn thấy opening đã nhập)
        today_snap = self._get_day_snapshot(company_id, bank_id, date_)

        if prev_closing is None:
            line.need_manual_opening = True
            # ưu tiên: user nhập trên wizard -> nếu chưa nhập thì lấy opening đã lưu ở snapshot ngày đó (nếu có)
            opening = (line.opening_manual or 0.0)
            if not opening and today_snap:
                opening = today_snap.opening_balance or 0.0
                line.opening_manual = opening
        else:
            line.need_manual_opening = False
            opening = prev_closing

        end_date = self._get_end_date_for_chain(company_id, bank_id, date_)

        d = date_
        cur_open = opening
        while d <= end_date:
            thu = self._sum_receipts(company_id, bank_id, d)
            chi = self._sum_payments(company_id, bank_id, d)
            closing = cur_open + thu - chi

            # IMPORTANT: lưu cả opening & closing cho từng ngày -> mở lại 01/01 vẫn thấy opening
            self._upsert_snapshot(company_id, bank_id, d, cur_open, closing)

            if d == date_:
                line.opening_balance = cur_open
                line.receipt_amount = thu
                line.payment_amount = chi
                line.closing_balance = closing

            cur_open = closing
            d = d + timedelta(days=1)

    # -------------------------
    # onchange
    # -------------------------
    @api.onchange("date", "company_id")
    def _onchange_date_company(self):
        for w in self:
            w._rebuild_lines()

    # -------------------------
    # action
    # -------------------------
    def action_generate_report(self):
        self.ensure_one()
        self._cleanup_empty_lines()

        if not self.line_ids:
            self._rebuild_lines()
        else:
            for l in self.line_ids:
                self._recalc_one_line(l)

        data = {
            "date": self.date.strftime("%d/%m/%Y") if self.date else "",
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "lines": [
                {
                    "bank_name": l.bank_id.name or "",
                    "opening_balance": l.opening_balance or 0.0,
                    "receipt_amount": l.receipt_amount or 0.0,
                    "payment_amount": l.payment_amount or 0.0,
                    "closing_balance": l.closing_balance or 0.0,
                }
                for l in self.line_ids
                if l.bank_id
            ],
        }
        return self.env.ref("bank_balance.report_bank_daily_balance_html").report_action(self, data=data)


class BankBalanceWizardLine(models.TransientModel):
    _name = "bank.balance.wizard.line"
    _description = "Wizard Line - Bank Balance"

    wizard_id = fields.Many2one("bank.balance.wizard", required=True, ondelete="cascade")

    # Fix lỗi thiếu currency khi tạo line: lấy trực tiếp từ wizard (bạn đã gặp lỗi này)
    # (cách này giống phần fix trong file bạn đang có) :contentReference[oaicite:1]{index=1}
    currency_id = fields.Many2one(
        "res.currency",
        related="wizard_id.currency_id",
        readonly=True,
        store=False,
    )

    # Không required để tránh lỗi autosave khi có dòng mới chưa chọn bank (bạn bấm nút là dính)
    bank_id = fields.Many2one("res.bank", string="Ngân hàng", required=False)

    need_manual_opening = fields.Boolean(string="Cần nhập tồn đầu?", readonly=True)

    opening_manual = fields.Monetary(
        string="Tồn đầu nhập",
        currency_field="currency_id",
        default=0.0,
    )

    opening_balance = fields.Monetary(string="Tồn đầu ngày", currency_field="currency_id", readonly=True)
    receipt_amount = fields.Monetary(string="PS thu", currency_field="currency_id", readonly=True)
    payment_amount = fields.Monetary(string="PS chi", currency_field="currency_id", readonly=True)
    closing_balance = fields.Monetary(string="Tồn cuối ngày", currency_field="currency_id", readonly=True)

    @api.onchange("opening_manual")
    def _onchange_opening_manual(self):
        for line in self:
            if line.wizard_id:
                line.wizard_id._recalc_one_line(line)
