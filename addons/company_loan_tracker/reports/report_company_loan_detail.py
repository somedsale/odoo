# -*- coding: utf-8 -*-
from odoo import models, api, fields
import datetime


class ReportCompanyLoanDetail(models.AbstractModel):
    _name = 'report.company_loan_tracker.report_company_loan_detail_view'
    _description = 'Báo cáo chi tiết khoản vay theo bên cho vay'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        lender_id   = data.get('lender_id')
        date_from_s = data.get('date_from') or False
        date_to_s   = data.get('date_to') or False

        # Chỉ dùng cho header
        date_from = fields.Date.to_date(date_from_s) if date_from_s else None
        date_to   = fields.Date.to_date(date_to_s) if date_to_s else None

        Loan    = self.env['company.loan']
        Payment = self.env['account.payment.request']

        # Lấy tất cả khoản vay của bên cho vay
        loans = Loan.search([('lender_id', '=', lender_id)])
        loan_ids = loans.ids or [0]

        # Lấy toàn bộ phiếu chi thuộc các khoản vay này
        payments = Payment.search(
            [('loan_id', 'in', loan_ids)],
            order="loan_id, date_payment asc, create_date asc"
        )

        rows = []
        # Gom theo loan_id để tính nợ giảm dần riêng cho từng khoản vay
        grouped = {}
        for p in payments:
            grouped.setdefault(p.loan_id.id, []).append(p)

        # Xử lý từng nhóm
        for loan_id, pay_list in grouped.items():
            loan = loans.filtered(lambda l: l.id == loan_id)
            if not loan:
                continue
            loan = loan[0]

            remaining_principal = loan.amount or 0.0  # Nợ gốc ban đầu
            currency = loan.currency_id or self.env.company.currency_id

            for p in pay_list:
                pay_date = p.date_payment or (p.create_date and p.create_date.date())

                # Giảm nợ gốc nếu là phiếu chi trả gốc
                if p.loan_payment_kind == 'principal':
                    remaining_principal -= p.total or 0.0
                    if remaining_principal < 0:
                        remaining_principal = 0.0

                # Tính lãi còn nợ động
                interest_due = getattr(p, 'interest_expected', 0.0) or 0.0
                interest_paid = p.total if p.loan_payment_kind == 'interest' else 0.0
                remaining_interest = max(interest_due - interest_paid, 0.0)

                rows.append({
                    'loan_name': loan.name or '',
                    'loan_amount': loan.amount or 0.0,
                    'loan_interest_rate': loan.interest_rate or 0.0,
                    'loan_start_date': loan.start_date,
                    'loan_due_date': loan.due_date,
                    'date': pay_date,
                    'kind': p.loan_payment_kind or 'other',
                    'total': p.total or 0.0,
                    'interest_expected': interest_due,
                    'interest_shortfall': getattr(p, 'interest_shortfall', 0.0) or 0.0,
                    'date_from': getattr(p, 'date_from', False),
                    'date_to': getattr(p, 'date_to', False),
                    'interest_days': getattr(p, 'interest_days', 0) or 0,
                    'state': p.state,
                    'currency': currency,
                    # ✅ Nợ gốc và nợ lãi tính động
                    'loan_balance': remaining_principal,
                    'loan_interest_outstanding': remaining_interest,
                })

        return {
            'doc_ids': [],
            'doc_model': 'company.loan',
            'res_company': self.env.company,
            'user_id': self.env.user,
            'datetime': datetime,
            'lender': self.env['res.partner'].browse(lender_id),
            'date_from': date_from_s,
            'date_to': date_to_s,
            'rows': rows,
        }
