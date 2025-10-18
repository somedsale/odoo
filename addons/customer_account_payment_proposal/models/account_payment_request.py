from odoo import models, fields

class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    payment_proposal_id = fields.Many2one('account.payment.proposal', string="Đề nghị giải chi")
