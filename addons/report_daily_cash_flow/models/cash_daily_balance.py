# -*- coding: utf-8 -*-
from odoo import models, fields


class CashDailyBalance(models.Model):
    _name = "cash.daily.balance"
    _description = "Daily Closing Balance Bank/Cash"
    _order = "date desc, id desc"
    _rec_name = "date"

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    date = fields.Date(
        string="Ngày",
        required=True,
        index=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    closing_bank = fields.Monetary(
        string="Tồn cuối - Ngân hàng",
        currency_field="currency_id",
        default=0.0,
    )

    closing_cash = fields.Monetary(
        string="Tồn cuối - Tiền mặt",
        currency_field="currency_id",
        default=0.0,
    )

    _sql_constraints = [
        (
            "uniq_company_date",
            "unique(company_id, date)",
            "Đã có tồn cuối cho ngày này trong công ty này.",
        )
    ]