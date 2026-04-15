from odoo import models, fields, api, http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(string="Mã phiếu chi", required=True, copy=False, readonly=True, default='/')

    # GIỮ FIELD CŨ để không mất dữ liệu cũ
    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất (cũ)")
    proposal_person_id = fields.Many2one('res.users', string="Người đề xuất", store=True)
    total = fields.Float(string="Số tiền", compute='_compute_total', store=True, readonly=False)
    manual_total = fields.Float(string="Số tiền (nhập tay)", store=True, readonly=False)  # chỉ để nhập liệu, không dùng tính toán gì cả
    date = fields.Date(string="Ngày đề xuất")
    date_payment = fields.Date(string="Ngày thanh toán")
    journal_id = fields.Many2one('account.journal', string="Nhật ký", domain="[('type', 'in', ['cash', 'bank'])]")
    project_id = fields.Many2one('project.project', string="Dự án", store=True)
    is_confirmed = fields.Boolean(string="Đã chi", default=False)
    receive_person = fields.Many2one('res.partner', string="Người nhận tiền")
    payment_person = fields.Many2one('res.partner', string="Người tạo chi")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    cost_classification = fields.Selection([
        ('employee', 'Khoản vay nội bộ(nhân viên)'),
        ('office', 'Chi phí tại công ty'),
        ('project', 'Chi phí các công trình'),
        ('fixed_cost', 'Chi phí cố định'),
        ('irregular_expenses', 'Chi phí không thường xuyên'),
        ('loan_interest', 'Chi phí trả lãi vay'),
    ], string="Phân loại chi phí", default='employee', required=True)

    expense_category_id = fields.Many2one(
        'expense.category',
        string="Khoản mục",
        domain="[('classification', '=', cost_classification)]",
        help="Chọn khoản mục chi tiết phù hợp với Phân loại chi phí."
    )

    expense_type = fields.Selection([
        ('material', 'Nguyên vật liệu'),
        ('labor', 'Nhân công'),
        ('manufacturing', 'Sản xuất chung'),
    ], string="Loại chi phí", default='material', required=True)

    payment_type = fields.Selection([
        ('cash', 'Tiền mặt'),
        ('bank', 'Chuyển khoản')
    ], string="Loại thanh toán", default='cash', required=True)

    bankids = fields.Many2one('res.partner.bank', string="Tài khoản người nhận", domain="[('partner_id', '=', receive_person)]")
    note = fields.Text(string="Diễn giải")

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

    bank_id = fields.Many2one('res.bank', string="Ngân hàng")

    # MỚI: nhiều phiếu đề xuất trong 1 phiếu chi
    line_ids = fields.One2many(
        'account.payment.request.line',
        'payment_request_id',
        string='Chi tiết phiếu đề xuất',
        copy=True
    )

    proposal_count = fields.Integer(
        string='Số phiếu đề xuất',
        compute='_compute_proposal_count',
        store=True
    )
    proposal_sheet_names = fields.Char(
        string='Phiếu đề xuất',
        compute='_compute_proposal_sheet_names',
        store=True
    )
    @api.depends('line_ids', 'line_ids.proposal_sheet_id', 'line_ids.proposal_sheet_id.name')
    def _compute_proposal_sheet_names(self):
        for rec in self:
            names = rec.line_ids.mapped('proposal_sheet_id.name')
            rec.proposal_sheet_names = ', '.join(names) if names else (
                rec.proposal_sheet_id.name if rec.proposal_sheet_id else False
            )
    @api.depends('line_ids.amount', 'manual_total')
    def _compute_total(self):
        for rec in self:
            if rec.line_ids:
                rec.total = sum(rec.line_ids.mapped('amount')) + (rec.manual_total or 0.0)
            else:
                # fallback dữ liệu cũ
                rec.total = (rec.total or 0.0) + (rec.manual_total or 0.0)

    @api.depends('line_ids')
    def _compute_proposal_count(self):
        for rec in self:
            rec.proposal_count = len(rec.line_ids)

    @api.onchange('cost_classification')
    def _onchange_cost_classification(self):
        for rec in self:
            rec.expense_category_id = False

    @api.onchange('proposal_sheet_id')
    def _onchange_proposal_sheet_id(self):
        """
        Tương thích dữ liệu cũ:
        nếu chọn proposal_sheet_id cũ ở draft và chưa có line -> tạo 1 line mặc định
        """
        for rec in self:
            if rec.proposal_sheet_id and not rec.line_ids and rec.state == 'draft':
                rec.project_id = rec.proposal_sheet_id.project_id
                rec.proposal_person_id = rec.proposal_sheet_id.requested_by
                rec.date = rec.proposal_sheet_id.date_proposal
                rec.line_ids = [(0, 0, {
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': rec.total or rec.proposal_sheet_id.amount_total or 0.0,
                })]

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        for rec in self:
            if rec.line_ids:
                projects = rec.line_ids.mapped('project_id')
                if len(projects) == 1:
                    rec.project_id = projects[0].id
                first_line = rec.line_ids[0]
                rec.proposal_sheet_id = first_line.proposal_sheet_id.id
                rec.proposal_person_id = first_line.proposal_sheet_id.requested_by.id
                rec.date = first_line.proposal_sheet_id.date_proposal
            else:
                rec.proposal_sheet_id = False
                rec.proposal_person_id = False
                rec.date = False

    @api.constrains('line_ids', 'project_id')
    def _check_lines_same_project(self):
        for rec in self:
            if not rec.line_ids:
                continue
            projects = rec.line_ids.mapped('project_id')
            if len(projects) > 1:
                raise ValidationError("Một phiếu chi chỉ được gom các phiếu đề xuất trong cùng một dự án.")
            if rec.project_id and projects and rec.project_id != projects[0]:
                raise ValidationError("Dự án trên phiếu chi phải trùng với dự án của các phiếu đề xuất.")

    @api.constrains('line_ids')
    def _check_has_lines_before_confirm(self):
        for rec in self:
            if rec.state in ('confirmed', 'post', 'done') and not rec.line_ids:
                raise ValidationError("Phiếu chi phải có ít nhất một dòng phiếu đề xuất.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('account.payment.request')

        records = super().create(vals_list)

        # migrate mềm cho dữ liệu/luồng cũ:
        # có proposal_sheet_id nhưng chưa có line => tạo line đầu tiên
        for rec in records:
            if rec.proposal_sheet_id and not rec.line_ids:
                rec.line_ids = [(0, 0, {
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': rec.total or rec.proposal_sheet_id.amount_total or 0.0,
                })]
                rec._sync_header_from_lines()
        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.proposal_sheet_id and not rec.line_ids:
                rec.line_ids = [(0, 0, {
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': rec.total or rec.proposal_sheet_id.amount_total or 0.0,
                })]
            rec._sync_header_from_lines()
        return res

    def _sync_header_from_lines(self):
        for rec in self:
            if rec.line_ids:
                first = rec.line_ids[0]
                values = {
                    'proposal_sheet_id': first.proposal_sheet_id.id,
                    'proposal_person_id': first.proposal_sheet_id.requested_by.id if first.proposal_sheet_id.requested_by else False,
                    'date': first.proposal_sheet_id.date_proposal,
                }
                projects = rec.line_ids.mapped('project_id')
                values['project_id'] = projects[0].id if len(projects) == 1 else False
                super(AccountingPaymentRequest, rec).write(values)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError("Bạn phải chọn ít nhất 1 phiếu đề xuất.")
            if any(line.amount <= 0 for line in rec.line_ids):
                raise UserError("Số tiền chi trên từng phiếu đề xuất phải lớn hơn 0.")
            if not rec.total or rec.total <= 0:
                raise UserError("Bạn phải nhập số tiền trước khi hoàn tất.")
            if rec.state == 'draft':
                rec.state = 'confirmed'

    def action_post(self):
        for rec in self:
            if rec.state == 'confirmed':
                rec.state = 'post'

    def action_cancel(self):
        for rec in self:
            rec.state = 'cancelled'

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state == 'cancelled':
                rec.state = 'draft'
                rec._cleanup_after_confirm()

    def _cleanup_after_confirm(self):
        for rec in self:
            cash_flows = self.env['project.cash.flow'].search([('account_payment_id', '=', rec.id)])
            if cash_flows:
                cash_flows.unlink()

            rec.write({
                'status_expense': 'not yet',
                'is_confirmed': False,
                'payment_person': False,
                'date_payment': False,
            })

            if rec.project_id:
                dashboard = self.env['project.expense.dashboard'].search([('project_id', '=', rec.project_id.id)])
                if dashboard:
                    dashboard._compute_total_actual()

    def action_payment_request(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise UserError("Yêu cầu chi tiền chỉ có thể được đánh dấu là đã hoàn tất khi ở trạng thái xác nhận.")

            rec.state = 'done'
            rec.status_expense = 'paid'
            rec.payment_person = self.env.user.partner_id
            rec.date_payment = fields.Datetime.now()
            rec.message_post(body="Yêu cầu chi tiền đã hoàn tất.")

            # cập nhật trạng thái từng proposal.sheet theo tổng đã chi DONE
            for line in rec.line_ids:
                proposal = line.proposal_sheet_id
                all_payment_lines = self.env['account.payment.request.line'].search([
                    ('proposal_sheet_id', '=', proposal.id),
                    ('payment_request_id.state', '=', 'done')
                ])
                total_paid = sum(all_payment_lines.mapped('amount'))

                if total_paid >= (proposal.amount_total or 0.0):
                    proposal.state = 'done'

            dashboard = self.env['project.expense.dashboard'].search([('project_id', '=', rec.project_id.id)])
            if dashboard:
                dashboard._compute_total_actual()

            if rec.cost_classification == 'project' and rec.project_id:
                self.env['project.cash.flow'].create({
                    'project_id': rec.project_id.id,
                    'partner_id': rec.project_id.partner_id.id if rec.project_id.partner_id else False,
                    'type': 'out',
                    'amount': rec.total,
                    'currency_id': rec.currency_id.id if rec.currency_id else self.env.company.currency_id.id,
                    'date': rec.date_payment or fields.Date.today(),
                    'account_payment_id': rec.id
                })
    def action_sync_old_payment_requests(self):
        payments = self.env['account.payment.request'].search([
            ('proposal_sheet_id', '!=', False),
        ])

        created_count = 0
        for payment in payments:
            if payment.line_ids:
                continue

            self.env['account.payment.request.line'].create({
                'payment_request_id': payment.id,
                'proposal_sheet_id': payment.proposal_sheet_id.id,
                'amount': payment.total if payment.total is not None else 0.0,
            })

            if hasattr(payment, '_sync_header_from_lines'):
                payment._sync_header_from_lines()

            created_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Đồng bộ thành công'),
                'message': _('Đã tạo %s dòng phiếu đề xuất cho các phiếu chi cũ.') % created_count,
                'type': 'success',
                'sticky': False,
            }
        }

class PaymentRequestController(http.Controller):
    @http.route('/payment_request/statistics', type='json', auth='user')
    def get_statistics(self):
        domain = [('state', '!=', 'draft')]
        records = request.env['account.payment.request'].search(domain)

        spent = sum(rec.total for rec in records if rec.state in ['post', 'done'])
        not_spent = sum(rec.total for rec in records if rec.state == 'confirmed')

        return {
            'spent': spent,
            'not_spent': not_spent,
        }