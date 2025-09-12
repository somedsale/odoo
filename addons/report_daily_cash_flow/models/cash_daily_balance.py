# models/cash_daily_balance.py
from odoo import models, fields, api
from odoo.exceptions import ValidationError

class CashDailyBalance(models.Model):
    _name = 'cash.daily.balance'
    _description = 'Daily Closing Balance (Bank/Cash)'
    _order = 'date desc, id desc'
    _rec_name = 'date'

    date = fields.Date(required=True, index=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    closing_bank = fields.Monetary(currency_field='currency_id', string='Closing Bank', default=0.0)
    closing_cash = fields.Monetary(currency_field='currency_id', string='Closing Cash', default=0.0)

    _sql_constraints = [
        ('uniq_company_date', 'unique(date)', 'Đã có tồn cuối cho ngày này trong công ty này.')
    ]
