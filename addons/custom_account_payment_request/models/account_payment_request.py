from odoo import models, fields, api

class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'

    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất", required=True)
    total = fields.Monetary(string="Số tiền", currency_field='currency_id', required=True)
    date = fields.Date(string="Ngày chi", default=fields.Date.today)
    journal_id = fields.Many2one('account.journal', string="Nhật ký", domain="[('type', 'in', ['cash', 'bank'])]")
    project_id = fields.Many2one('project.project', string="Dự án")
    is_confirmed = fields.Boolean(string="Đã chi", default=False)
    company_id = fields.Many2one(
    'res.company',
    string='Công ty',
    required=True,
    default=lambda self: self.env.company
)
    currency_id = fields.Many2one(
    'res.currency',
    string="Tiền tệ",
    compute='_compute_currency_id',
    store=True,
    readonly=True
)
    stage = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('post', 'Đã vào sổ'),
        ('cancelled', 'Hủy'),
        ('done', 'Hoàn tất'),
    ], default='draft')
    def button_confirm_payment(self):
        for rec in self:
            if not rec.is_confirmed:
                rec.is_confirmed = True
                rec.proposal_sheet_id.state = 'done'
    @api.depends('company_id')
    def _compute_currency_id(self):
        for rec in self:
            rec.currency_id = rec.company_id.currency_id