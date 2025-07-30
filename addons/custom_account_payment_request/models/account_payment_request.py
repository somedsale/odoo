from odoo import models, fields, api

class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'

    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất", required=True)
    amount = fields.Float(string="Số tiền", required=True)
    date = fields.Date(string="Ngày chi", default=fields.Date.today)
    journal_id = fields.Many2one('account.journal', string="Nhật ký", domain="[('type', 'in', ['cash', 'bank'])]")
    project_id = fields.Many2one('project.project', string="Dự án")
    is_confirmed = fields.Boolean(string="Đã chi", default=False)


    def button_confirm_payment(self):
        for rec in self:
            if not rec.is_confirmed:
                rec.is_confirmed = True
                rec.proposal_sheet_id.state = 'done'