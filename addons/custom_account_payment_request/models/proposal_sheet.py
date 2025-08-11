from odoo import models, fields

class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    payment_ids = fields.One2many(
        'account.payment.request',     # model phiếu chi
        'proposal_sheet_id',         # field Many2one bên account.payment
        string='Phiếu Chi'
    )
