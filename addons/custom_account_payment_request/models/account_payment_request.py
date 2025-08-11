from odoo import models, fields, api,http
from odoo.exceptions import UserError
from odoo.http import request
class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(string="Mã phiếu chi", required=True, copy=False, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('account.payment.request'))
    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất")
    proposal_person_id = fields.Many2one('res.users', string="Người đề xuất", store=True)
    total = fields.Float(string="Số tiền")
    date = fields.Date(string="Ngày đề xuất", default=fields.Date.today)
    date_payment = fields.Date(string="Ngày thanh toán")
    journal_id = fields.Many2one('account.journal', string="Nhật ký", domain="[('type', 'in', ['cash', 'bank'])]")
    project_id = fields.Many2one('project.project', string="Dự án", store=True)
    is_confirmed = fields.Boolean(string="Đã chi", default=False)
    receive_person = fields.Many2one('res.partner', string="Người nhận tiền")
    payment_person = fields.Many2one('res.partner', string="Người tạo chi")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    payment_type = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('bank', 'Chuyển khoản'),
        ('other', 'Khác')
    ], string="Loại thanh toán", default='cash')
    bankids = fields.Many2one('res.partner.bank', string="Tài khoản ngân hàng" , domain="[('partner_id', '=', receive_person)]")
    note = fields.Text(string="Ghi chú")
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('post', 'Đã vào sổ'),
        ('cancelled', 'Hủy'),
        ('done', 'Hoàn tất'),
    ], default='draft')
    status_expense = fields.Selection([
        ('not yet', 'Chưa chi'),
        ('paid', 'Đã chi'),
    ], default='not yet')
    
    @api.onchange('proposal_sheet_id')
    def _onchange_proposal_sheet_id(self):
        for rec in self:
            if rec.proposal_sheet_id:
                rec.project_id = rec.proposal_sheet_id.project_id
                rec.proposal_person_id = rec.proposal_sheet_id.requested_by
    def button_confirm_payment(self):
        for rec in self:
            if not rec.is_confirmed:
                rec.is_confirmed = True
                rec.proposal_sheet_id.state = 'done'
    def action_confirm(self):
        for rec in self:
            if not rec.total or rec.total <= 0:
                raise UserError("Bạn phải nhập số tiền trước khi hoàn tất.")
            if rec.state == 'draft':
                rec.state = 'confirmed'          
    def action_post(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.state = 'post'
                # Logic to post the payment request to the accounting system
                # This could involve creating journal entries, etc.
    def action_cancel(self):
        for rec in self:
            if rec.state in ['draft', 'confirmed']:
                rec.state = 'cancelled'
            elif rec.state == 'post':
                raise UserError("Không thể hủy yêu cầu chi tiền đã vào sổ.")
            elif rec.state == 'done':
                raise UserError("Không thể hủy yêu cầu chi tiền đã hoàn tất.")
    def action_payment_request(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.state = 'done'
                # Logic to mark the payment request as done
                # This could involve updating related records, etc.
                if rec.proposal_sheet_id:
                    all_payments = self.env['account.payment.request'].search([
                        ('proposal_sheet_id', '=', rec.proposal_sheet_id.id)
                    ])

                    # Tổng tiền của các phiếu chi đã done
                    total_paid = sum(p.total for p in all_payments if p.state == 'done')

                    # Nếu tổng đã chi >= tổng đề xuất -> done
                    if total_paid >= rec.proposal_sheet_id.amount_total:  # total_amount là field tổng tiền PĐX
                        rec.proposal_sheet_id.state = 'done'
                rec.status_expense = 'paid'
                rec.payment_person = self.env.user.partner_id
                rec.date_payment = fields.Datetime.now()
                rec.message_post(body="Yêu cầu chi tiền đã hoàn tất.")
                expense = self.env['project.expense.custom'].search([('project_id', '=', rec.project_id.id)], limit=1)
                if expense:
                    expense._compute_costs()
                dashboard = self.env['project.expense.dashboard'].search([('project_id', '=', rec.project_id.id)])
                dashboard._compute_total_actual()
                self.env['project.cash.flow'].create({
                        'project_id': rec.project_id.id,
                        'partner_id': rec.project_id.partner_id.id if rec.project_id.partner_id else False,
                        'type': 'out',
                        'amount': rec.total,
                        'currency_id': rec.currency_id.id if rec.currency_id else self.env.company.currency_id.id,
                        'date': rec.date_payment or fields.Date.today(),
                        'account_payment_id': rec.id
                    })
            else:
                raise UserError("Yêu cầu chi tiền chỉ có thể được đánh dấu là đã hoàn tất khi ở trạng thái đã vào sổ.")
class PaymentRequestController(http.Controller):
    @http.route('/payment_request/statistics', type='json', auth='user')
    def get_statistics(self):
        domain = [('state', '!=', 'draft')]  # lọc các bản ghi hợp lệ
        records = request.env['account.payment.request'].search(domain)

        spent = sum(rec.amount for rec in records if rec.state in ['approved', 'done'])
        not_spent = sum(rec.amount for rec in records if rec.state == 'submitted')

        return {
            'spent': spent,
            'not_spent': not_spent,
        }