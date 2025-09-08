from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    amount_in_words = fields.Char(string="Số tiền bằng chữ", compute="_compute_amount_in_words")

    @api.depends('total', 'currency_id')
    def _compute_amount_in_words(self):
        for rec in self:
            rec.amount_in_words = rec.amount_to_text()

    def amount_to_text(self):
        """Chuyển số tiền sang chữ theo currency của phiếu chi"""
        self.ensure_one()
        if not self.total:
            return ''
        return self.currency_id.amount_to_text(self.total)
