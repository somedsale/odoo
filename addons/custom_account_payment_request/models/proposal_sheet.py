from odoo import models, fields, api

class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    payment_ids = fields.One2many(
        'account.payment.request',     # model phiếu chi
        'proposal_sheet_id',         # field Many2one bên account.payment
        string='Phiếu Chi'
    )
    payment_total = fields.Float(string="Tổng phiếu chi", compute='_compute_payment_total')
    @api.depends('payment_ids')
    def _compute_payment_total(self):
        for record in self:
            record.payment_total = sum(record.payment_ids.mapped('total'))

    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)