from odoo import models, fields, api, http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request


class AccountingPaymentRequest(models.Model):
    _name = 'account.payment.request'
    _description = 'Yêu cầu chi tiền kế toán'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"

    name = fields.Char(string="Mã phiếu chi", required=True, copy=False, readonly=True, default='/')

    # =========================
    # Liên kết bổ sung để tạo từ PO
    # =========================
    purchase_id = fields.Many2one(
        'purchase.order',
        string='Đơn mua hàng',
        ondelete='set null',
        index=True
    )

    supplier_contract_id = fields.Many2one(
        'supplier.contract',
        string='Hợp đồng NCC',
        ondelete='set null'
    )

    task_id = fields.Many2one(
        'project.task',
        string='Nhiệm vụ',
        ondelete='set null'
    )

    supplier_id = fields.Many2one(
        'res.partner',
        string='Nhà cung cấp',
        ondelete='set null'
    )

    payment_kind = fields.Selection([
        ('advance', 'Tạm ứng'),
        ('full', 'Thanh toán toàn bộ'),
    ], string='Kiểu thanh toán', default='full', tracking=True)

    # giữ để tương thích dữ liệu cũ
    proposal_sheet_id = fields.Many2one('proposal.sheet', string="Phiếu đề xuất (cũ)")
    proposal_person_id = fields.Many2one('res.users', string="Người đề xuất", store=True)

    total = fields.Float(string="Số tiền", compute='_compute_total', store=True)
    manual_total = fields.Float(string="Số tiền nhập tay", default=0.0)

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
    ], default='draft', tracking=True)

    status_expense = fields.Selection([
        ('not yet', 'Chưa chi'),
        ('paid', 'Đã chi'),
    ], default='not yet')

    bank_id = fields.Many2one('res.bank', string="Ngân hàng")

    line_ids = fields.One2many(
        'account.payment.request.line',
        'payment_request_id',
        string='Chi tiết phiếu chi',
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

    is_manual_payment = fields.Boolean(
        string='Chi thủ công',
        compute='_compute_is_manual_payment',
        store=True
    )

    @api.depends('line_ids')
    def _compute_is_manual_payment(self):
        for rec in self:
            rec.is_manual_payment = not bool(rec.line_ids)

    @api.depends('line_ids.proposal_sheet_id', 'line_ids.proposal_sheet_id.name')
    def _compute_proposal_sheet_names(self):
        for rec in self:
            proposal_lines = rec.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.proposal_sheet_id)
            names = proposal_lines.mapped('proposal_sheet_id.name')
            rec.proposal_sheet_names = ', '.join(names) if names else False

    @api.depends('line_ids.amount', 'manual_total')
    def _compute_total(self):
        for rec in self:
            if rec.line_ids:
                rec.total = sum(rec.line_ids.mapped('amount'))
            else:
                rec.total = rec.manual_total or 0.0

    @api.depends('line_ids')
    def _compute_proposal_count(self):
        for rec in self:
            rec.proposal_count = len(rec.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.proposal_sheet_id))

    @api.onchange('cost_classification')
    def _onchange_cost_classification(self):
        for rec in self:
            rec.expense_category_id = False

    @api.onchange('proposal_sheet_id')
    def _onchange_proposal_sheet_id(self):
        for rec in self:
            if rec.proposal_sheet_id and not rec.line_ids and rec.state == 'draft':
                amount = rec.proposal_sheet_id.amount_total or rec.manual_total or 0.0
                rec.line_ids = [(0, 0, {
                    'line_type': 'proposal',
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': amount,
                })]
                rec._sync_header_from_lines()

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        for rec in self:
            rec._sync_header_from_lines()

    def _get_header_vals_from_lines(self):
        self.ensure_one()
        proposal_lines = self.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.proposal_sheet_id)

        if not proposal_lines:
            return {
                'proposal_sheet_id': False,
                'proposal_person_id': False,
                'date': False,
                'project_id': False,
            }

        first = proposal_lines[0]
        projects = proposal_lines.mapped('project_id')

        return {
            'proposal_sheet_id': first.proposal_sheet_id.id,
            'proposal_person_id': first.proposal_sheet_id.requested_by.id if first.proposal_sheet_id.requested_by else False,
            'date': first.proposal_sheet_id.date_proposal,
            'project_id': projects[0].id if len(projects) == 1 else False,
        }

    def _sync_header_from_lines(self):
        for rec in self:
            values = rec._get_header_vals_from_lines()
            for field_name, value in values.items():
                rec[field_name] = value

    @api.constrains('line_ids', 'project_id')
    def _check_lines_same_project(self):
        for rec in self:
            proposal_lines = rec.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.project_id)
            if not proposal_lines:
                continue

            projects = proposal_lines.mapped('project_id')
            if len(projects) > 1:
                raise ValidationError("Một phiếu chi chỉ được gom các phiếu đề xuất trong cùng một dự án.")

            if rec.project_id and rec.project_id != projects[0]:
                raise ValidationError("Dự án trên phiếu chi phải trùng với dự án của các phiếu đề xuất.")

    @api.constrains('manual_total')
    def _check_manual_total(self):
        for rec in self:
            if rec.manual_total < 0:
                raise ValidationError("Số tiền nhập tay không được âm.")

    @api.constrains('line_ids', 'manual_total')
    def _check_payment_source(self):
        for rec in self:
            if not rec.line_ids and (rec.manual_total or 0.0) <= 0:
                raise ValidationError("Bạn phải nhập ít nhất 1 dòng phiếu chi hoặc số tiền nhập tay lớn hơn 0.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('account.payment.request')

        records = super().create(vals_list)

        for rec in records:
            if rec.proposal_sheet_id and not rec.line_ids:
                amount = rec.manual_total or rec.proposal_sheet_id.amount_total or 0.0
                rec.line_ids = [(0, 0, {
                    'line_type': 'proposal',
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': amount,
                })]
            rec._write_header_from_lines()

        return records

    def write(self, vals):
        res = super().write(vals)
        for rec in self:
            if rec.proposal_sheet_id and not rec.line_ids and rec.state == 'draft':
                amount = rec.manual_total or rec.proposal_sheet_id.amount_total or 0.0
                rec.line_ids = [(0, 0, {
                    'line_type': 'proposal',
                    'proposal_sheet_id': rec.proposal_sheet_id.id,
                    'amount': amount,
                })]
            rec._write_header_from_lines()
        return res

    def _write_header_from_lines(self):
        for rec in self:
            values = rec._get_header_vals_from_lines()
            super(AccountingPaymentRequest, rec).write(values)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids and (rec.manual_total or 0.0) <= 0:
                raise UserError("Bạn phải chọn ít nhất 1 phiếu đề xuất hoặc nhập số tiền chi thủ công.")

            if rec.line_ids and any(line.amount <= 0 for line in rec.line_ids):
                raise UserError("Số tiền chi trên từng dòng phải lớn hơn 0.")

            if rec.total <= 0:
                raise UserError("Tổng số tiền chi phải lớn hơn 0.")

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

            if rec.total <= 0:
                raise UserError("Tổng số tiền chi phải lớn hơn 0.")

            rec.state = 'done'
            rec.status_expense = 'paid'
            rec.payment_person = self.env.user.partner_id
            rec.date_payment = fields.Datetime.now()
            rec.message_post(body="Yêu cầu chi tiền đã hoàn tất.")

            proposal_lines = rec.line_ids.filtered(lambda l: l.line_type == 'proposal' and l.proposal_sheet_id)
            for line in proposal_lines:
                proposal = line.proposal_sheet_id
                all_payment_lines = self.env['account.payment.request.line'].search([
                    ('proposal_sheet_id', '=', proposal.id),
                    ('line_type', '=', 'proposal'),
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

            amount = payment.manual_total or payment.total or payment.proposal_sheet_id.amount_total or 0.0

            self.env['account.payment.request.line'].create({
                'payment_request_id': payment.id,
                'line_type': 'proposal',
                'proposal_sheet_id': payment.proposal_sheet_id.id,
                'amount': amount,
            })

            payment._write_header_from_lines()
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