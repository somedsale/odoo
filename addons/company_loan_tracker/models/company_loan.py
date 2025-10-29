# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class CompanyLoan(models.Model):
    _name = 'company.loan'
    _description = 'Khoản vay của công ty'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # --- Thông tin cơ bản ---
    name = fields.Char(
        string='Mã giao dịch',
        required=True,
        copy=False,
        tracking=True,
        help="Nhập mã vay hoặc mã giao dịch thực tế (VD: VAY-2025-001)."
    )
    lender_id = fields.Many2one(
        'res.partner',
        string='Người cho vay',
        domain=[('is_lender', '=', True)],
        required=True,
        tracking=True
    )
    loan_type = fields.Selection(
    [
        ('personal', 'Vay cá nhân'),
        ('short_term', 'Vay ngắn hạn'),
        ('medium_term', 'Vay trung hạn'),
    ],
    string='Loại vay',
    default='personal',
    required=True,
    tracking=True,
)
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id
    )
    start_date = fields.Date(
        string='Ngày bắt đầu vay',
        tracking=True,
        help="Ngày bắt đầu tính khoản vay (ngày nhận tiền hoặc giải ngân)."
    )
    due_date = fields.Date(
        string='Ngày đáo hạn vay',
        tracking=True,
        help="Ngày dự kiến hoàn tất hoặc đáo hạn khoản vay."
    )

    # --- Thông tin tài chính ---
    amount = fields.Monetary(
        string='Tổng tiền vay (phiếu thu)',
        compute='_compute_loan_totals',
        store=True,
        tracking=True
    )
    total_paid = fields.Monetary(
        string='Tổng đã thanh toán (phiếu chi)',
        compute='_compute_loan_totals',
        store=True,
        tracking=True
    )
    balance = fields.Monetary(
        string='Còn nợ',
        compute='_compute_loan_totals',
        store=True,
        tracking=True
    )
    total_interest_paid = fields.Monetary(
        string='Tổng tiền trả lãi',
        compute='_compute_loan_totals',
        store=True,
        tracking=True
    )
    total_interest_due = fields.Monetary(
        string='Tổng lãi phải trả',
        compute='_compute_loan_totals',
        store=True,
        tracking=True,
        help="Tổng số lãi lẽ ra phải trả (nghĩa vụ lãi) theo các kỳ đã phát sinh."
    )

    interest_outstanding = fields.Monetary(
        string='Lãi còn nợ',
        compute='_compute_loan_totals',
        store=True,
        tracking=True,
        help="Phần lãi còn chưa thanh toán = Tổng lãi phải trả - Tổng lãi đã chi."
    )
    interest_rate = fields.Float(
        string='Lãi suất (%/năm)',
        tracking=True,
        help="Nhập lãi suất theo năm (ví dụ: 10 = 10%/năm)."
    )

    # --- Theo dõi thanh toán ---
    payment_request_ids = fields.One2many(
        'account.payment.request',
        'loan_id',
        string='Phiếu chi liên quan',
        help='Danh sách phiếu chi (trả nợ) liên kết với khoản vay này.'
    )
    receipt_ids = fields.One2many(
        'account.receipt',
        'loan_id',
        string='Phiếu thu liên quan',
        help='Danh sách phiếu thu (nhận tiền vay) liên kết với khoản vay này.'
    )

    # --- Ghi chú và mô tả ---
    interest_note = fields.Text(
        string='Ngày trả lãi/gốc (ghi chú)',
        help="Ví dụ: Trả lãi và gốc vào ngày 25 hàng tháng, hoặc ghi chú khác."
    )
    note = fields.Text(string='Ghi chú thêm')

    # --- Trạng thái ---
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('ongoing', 'Đang vay'),
        ('done', 'Hoàn tất'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft', tracking=True)
    @api.depends(
        'receipt_ids.amount',
        'receipt_ids.state',
        'payment_request_ids.total',
        'payment_request_ids.state',
        'payment_request_ids.loan_payment_kind',
        'payment_request_ids.interest_expected',
    )
    def _compute_loan_totals(self):
        """
        Gồm:
        - amount                = Tổng tiền đã nhận (phiếu thu hợp lệ)
        - total_paid            = Tổng gốc đã trả (phiếu chi loại 'principal')
        - balance               = Còn nợ gốc
        - total_interest_paid   = Tổng lãi đã chi thực tế (phiếu chi 'interest', lấy total)
        - total_interest_due    = Tổng lãi đáng lẽ phải trả (phiếu chi 'interest', lấy interest_expected)
        - interest_outstanding  = Lãi còn nợ = due - paid (nếu âm thì = 0)
        """
        for rec in self:
            Receipt = self.env['account.receipt']
            Payment = self.env['account.payment.request']

            # 1. Tổng tiền vay (nhận tiền) từ phiếu thu đã xác nhận
            receipts = Receipt.search([
                ('loan_id', '=', rec.id),
                ('state', 'not in', ('cancel', 'draft')),
            ])
            total_receipt = sum(receipts.mapped('amount'))

            # 2. Các phiếu chi HỢP LỆ cùng khoản vay này
            payments_all = Payment.search([
                ('loan_id', '=', rec.id),
                ('state', 'not in', ('cancel', 'draft')),
            ])

            # 2a. Tổng trả gốc
            payments_principal = payments_all.filtered(lambda p: p.loan_payment_kind == 'principal')
            total_payment_principal = sum(payments_principal.mapped('total'))

            # 2b. Tổng trả lãi thực tế
            payments_interest = payments_all.filtered(lambda p: p.loan_payment_kind == 'interest')
            total_payment_interest_real = sum(payments_interest.mapped('total'))

            # 2c. Tổng lãi phải trả (kỳ này lẽ ra phải trả)
            total_interest_should_pay = sum(payments_interest.mapped('interest_expected'))

            # 3. Tính lãi còn nợ
            unpaid_interest = total_interest_should_pay - total_payment_interest_real
            if unpaid_interest < 0:
                unpaid_interest = 0.0

            # 4. Gán kết quả vào record
            rec.amount = total_receipt
            rec.total_paid = total_payment_principal
            rec.balance = total_receipt - total_payment_principal

            rec.total_interest_paid = total_payment_interest_real
            rec.total_interest_due = total_interest_should_pay
            rec.interest_outstanding = unpaid_interest

    # --- Tính toán ---
    @api.depends('amount', 'total_paid')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.amount - rec.total_paid

    # --- Kiểm tra trùng mã vay ---
    @api.constrains('name')
    def _check_unique_name(self):
        for rec in self:
            if rec.name:
                duplicate = self.search([
                    ('name', '=', rec.name),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise ValidationError(
                        f"Mã giao dịch '{rec.name}' đã tồn tại trong hệ thống "
                        f"(Người cho vay: {duplicate.lender_id.name})."
                    )
