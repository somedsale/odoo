from odoo import models, fields, api, _

class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    amount_in_words = fields.Char(
        string="Số tiền bằng chữ",
        compute="_compute_amount_in_words"
    )

    @api.depends('total', 'currency_id')
    def _compute_amount_in_words(self):
        for rec in self:
            rec.amount_in_words = rec._amount_to_text_vietnamese()

    def _amount_to_text_vietnamese(self):
        """Chuyển số tiền sang chữ tiếng Việt (VND, USD, ...)"""
        self.ensure_one()
        if not self.total:
            return ''

        text = self.currency_id.amount_to_text(self.total)

        if self.currency_id.name == "VND":
            text = text.replace("Dong", "Đồng").replace("DONG", "Đồng")
        
        
        return text
