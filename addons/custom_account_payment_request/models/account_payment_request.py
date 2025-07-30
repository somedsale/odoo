from odoo import models, fields, api

class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'

    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất", required=True)
    total = fields.Float(string="Số tiền", required=True)
    date = fields.Date(string="Ngày chi", default=fields.Date.today)
    journal_id = fields.Many2one('account.journal', string="Nhật ký", domain="[('type', 'in', ['cash', 'bank'])]")
    project_id = fields.Many2one('project.project', string="Dự án")
    is_confirmed = fields.Boolean(string="Đã chi", default=False)
    total_display = fields.Char(string="Số tiền", compute="_compute_total_display")

    @api.depends('total')
    def _compute_total_display(self):
        for rec in self:
            rec.total_display = "{:,.2f} ₫".format(rec.total or 0.0)  
    stage = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('post', 'Đã vào sổ'),
        ('cancelled', 'Hủy'),
        ('done', 'Hoàn tất'),
    ], default='draft')
    @api.depends('journal_id')
    def _compute_currency_id(self):
        for pay in self:
            pay.currency_id = pay.journal_id.currency_id or pay.journal_id.company_id.currency_id
    def button_confirm_payment(self):
        for rec in self:
            if not rec.is_confirmed:
                rec.is_confirmed = True
                rec.proposal_sheet_id.state = 'done'