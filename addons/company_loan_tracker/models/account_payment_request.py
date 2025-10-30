# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    loan_id = fields.Many2one(
        'company.loan',
        string='Khoản vay liên quan',
        help="Chọn khoản vay nếu phiếu chi này là trả nợ cho người cho vay.",
        ondelete='set null',
        tracking=True
    )
    loan_payment_kind = fields.Selection([
    ('principal', 'Trả gốc'),
    ('interest', 'Trả lãi'),
    ('other', 'Không có'),
], string='Loại thanh toán khoản vay')

    date_from = fields.Date(string='Từ ngày', tracking=True)
    date_to = fields.Date(string='Đến ngày', tracking=True)
    interest_days = fields.Integer(string='Số ngày tính lãi', compute='_compute_interest_days', store=True)
    interest_expected = fields.Monetary(
        string='Lãi phải trả kỳ này',
        currency_field='currency_id',
        help="Số lãi theo kỳ này theo thỏa thuận (ví dụ lãi tháng). Chỉ dùng khi Loại thanh toán = Trả lãi."
    )

    # phần lãi còn thiếu của kỳ này
    interest_shortfall = fields.Monetary(
        string='Lãi còn thiếu kỳ này',
        currency_field='currency_id',
        compute='_compute_interest_shortfall',
        store=True,
        help="= Lãi phải trả kỳ này - Số tiền thực tế chi. Nếu âm thì coi như 0."
    )

    @api.depends('date_from', 'date_to', 'loan_payment_kind')
    def _compute_interest_days(self):
        """Tự động tính số ngày giữa từ ngày và đến ngày khi là phiếu chi trả lãi."""
        for rec in self:
            if rec.loan_payment_kind == 'interest' and rec.date_from and rec.date_to:
                delta = rec.date_to - rec.date_from
                # +1 nếu muốn tính cả ngày đầu (ví dụ: 1/1 - 1/1 = 1 ngày)
                rec.interest_days = delta.days + 1 if delta.days >= 0 else 0
            else:
                rec.interest_days = 0
    @api.depends('loan_payment_kind', 'interest_expected', 'total')
    def _compute_interest_shortfall(self):
        for rec in self:
            if rec.loan_payment_kind == 'interest' and rec.interest_expected:
                diff = rec.interest_expected - rec.total
                rec.interest_shortfall = diff if diff > 0 else 0.0
            else:
                rec.interest_shortfall = 0.0