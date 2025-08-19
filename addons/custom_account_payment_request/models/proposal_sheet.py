from odoo import models, fields

class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    payment_ids = fields.One2many(
        'account.payment.request',     # model phiếu chi
        'proposal_sheet_id',         # field Many2one bên account.payment
        string='Phiếu Chi'
    )
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)