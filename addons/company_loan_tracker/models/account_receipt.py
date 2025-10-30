# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountReceipt(models.Model):
    _inherit = 'account.receipt'

    loan_id = fields.Many2one(
        'company.loan',
        string='Khoản vay liên quan',
        help="Chọn khoản vay nếu phiếu chi này là trả nợ cho người cho vay.",
        ondelete='set null',
        tracking=True
    )
