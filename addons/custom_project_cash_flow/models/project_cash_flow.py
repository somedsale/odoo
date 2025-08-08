from odoo import models, fields, api

class ProjectCashFlow(models.Model):
    _name = 'project.cash.flow'
    _description = 'Dòng tiền dự án'

    name = fields.Char(string='Tên dòng tiền', required=True)
    date = fields.Date(string='Ngày', required=True, default=fields.Date.context_today)
    project_id = fields.Many2one('project.project', string='Dự án', required=True)
    partner_id = fields.Many2one('res.partner', string='Đối tác')
    type = fields.Selection([
        ('in', 'Thu'),
        ('out', 'Chi'),
    ], string='Loại dòng tiền', required=True)

    amount = fields.Monetary(string='Số tiền', required=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id)

    receipt_id = fields.Many2one('account.receipt', string='Phiếu thu')
    # account_payment_id = fields.Many2one('account.payment.request', string='Phiếu chi')  

    note = fields.Text(string='Ghi chú')

    # @api.onchange('receipt_id', 'account_payment_id')
    # def _onchange_linked_docs(self):
    #     if self.receipt_id:
    #         self.amount = self.receipt_id.amount
    #         self.partner_id = self.receipt_id.partner_id
    #         self.type = 'in'
        # elif self.account_payment_id:
        #     self.amount = self.account_payment_id.amount
        #     self.partner_id = self.account_payment_id.partner_id
        #     self.type = 'out'
