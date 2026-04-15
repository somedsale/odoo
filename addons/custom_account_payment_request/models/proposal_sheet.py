from odoo import models, fields, api


class ProposalSheet(models.Model):
    _inherit = 'proposal.sheet'

    payment_line_ids = fields.One2many(
        'account.payment.request.line',
        'proposal_sheet_id',
        string='Chi tiết phiếu chi'
    )

    payment_ids = fields.Many2many(
        'account.payment.request',
        compute='_compute_payment_ids',
        string='Phiếu chi',
        store=False
    )

    payment_total = fields.Float(
        string="Tổng tiền đã chi",
        compute='_compute_payment_total',
        store=False
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

    def _compute_payment_ids(self):
        for rec in self:
            rec.payment_ids = rec.payment_line_ids.mapped('payment_request_id')

    def _compute_payment_total(self):
        for rec in self:
            done_lines = rec.payment_line_ids.filtered(
                lambda l: l.line_type == 'proposal' and l.payment_request_id.state == 'done'
            )
            rec.payment_total = sum(done_lines.mapped('amount'))