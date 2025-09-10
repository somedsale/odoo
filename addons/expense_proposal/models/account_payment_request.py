from odoo import models, fields, api

class AccountPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    expense_proposal_id = fields.Many2one('expense.proposal', string='Phiếu đề xuất')
    expense_proposal_line_id = fields.Many2one('expense.proposal.line', string='Expense Proposal Line')
    proposal_display = fields.Char(string='Phiếu đề xuất', compute='_compute_proposal_display')
    scheduled_date = fields.Date(string='Ngày dự chi', default=fields.Date.today)
    @api.depends('expense_proposal_id', 'proposal_sheet_id')
    def _compute_proposal_display(self):
        for record in self:
            if record.proposal_sheet_id:
                record.proposal_display = record.proposal_sheet_id.name
            else:
                record.proposal_display = record.expense_proposal_id.name