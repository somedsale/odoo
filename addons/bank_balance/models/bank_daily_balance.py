# -*- coding: utf-8 -*-
from odoo import models, fields


class BankDailyBalance(models.Model):
    _name = "bank.daily.balance"
    _description = "Daily Balance Snapshot (By Bank)"
    _order = "date desc, bank_id asc, id desc"
    _rec_name = "date"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    date = fields.Date(required=True, index=True)

    bank_id = fields.Many2one(
        "res.bank",
        string="Ngân hàng",
        required=True,
        index=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    # NEW: lưu tồn đầu ngày để mở lại ngày đó vẫn thấy (đặc biệt là ngày đầu tiên)
    opening_balance = fields.Monetary(
        currency_field="currency_id",
        string="Số dư đầu ngày",
        default=0.0,
    )

    closing_balance = fields.Monetary(
        currency_field="currency_id",
        string="Số dư cuối ngày",
        default=0.0,
        help="Tồn cuối của ngày này = tồn đầu ngày sau.",
    )

    note = fields.Char(string="Ghi chú")

    _sql_constraints = [
        (
            "uniq_company_date_bank",
            "unique(company_id, date, bank_id)",
            "Đã có snapshot cho ngày này và ngân hàng này trong công ty này.",
        )
    ]
