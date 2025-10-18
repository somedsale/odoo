from odoo import models, fields

class AccountReceipt(models.Model):
    _inherit = 'account.receipt'

    payment_proposal_id = fields.Many2one('account.payment.proposal', string="Đề nghị giải chi")
