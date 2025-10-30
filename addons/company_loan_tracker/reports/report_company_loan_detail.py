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
        

        Loan    = self.env['company.loan']
        Payment = self.env['account.payment.request']

        # Lấy các khoản vay theo lender
        loans = Loan.search([('lender_id', '=', lender_id)], order="name asc")
        loan_ids = loans.ids or [0]

        # Lấy mọi phiếu chi của các khoản vay này (theo thứ tự tăng dần cho tính rollout)
        payments = Payment.search(
            [('loan_id', 'in', loan_ids)],
            order="loan_id, date_payment asc, create_date asc"
        )

        # Nhóm phiếu chi theo loan_id
        grouped = {}
        for p in payments:
            grouped.setdefault(p.loan_id.id, []).append(p)

        lines = []
        for loan in loans:
            pay_list = grouped.get(loan.id, [])
            if not pay_list:
                continue

            remaining_principal = loan.amount or 0.0  # nợ gốc ban đầu
            currency = loan.currency_id or self.env.company.currency_id

            payments_data = []
            # ----- Biến tổng hợp cho dòng tổng -----
            sum_total_paid = 0.0                   # Tổng "Số tiền chi"
            sum_interest_expected = 0.0            # Tổng "Lãi phải trả"
            sum_interest_outstanding = 0.0         # Tổng "Lãi còn nợ" (SỬA: cộng dồn, không lấy min/last)
            final_principal_balance = 0.0          # Nợ gốc cuối (không cộng dồn)
            # --------------------------------------

            for p in pay_list:
                pay_date = p.date_payment or (p.create_date and p.create_date.date())

                # Nếu là trả gốc -> giảm nợ gốc
                if p.loan_payment_kind == 'principal':
                    remaining_principal -= (p.total or 0.0)
                    if remaining_principal < 0:
                        remaining_principal = 0.0

                # Lãi phải trả & lãi còn nợ (kỳ này)
                interest_due = getattr(p, 'interest_expected', 0.0) or 0.0
                interest_paid = p.total if p.loan_payment_kind == 'interest' else 0.0
                remaining_interest = max(interest_due - interest_paid, 0.0)

                # Cộng dồn cho dòng tổng
                sum_total_paid += (p.total or 0.0)
                sum_interest_expected += interest_due
                sum_interest_outstanding += remaining_interest         # <-- quan trọng
                final_principal_balance = remaining_principal          # luôn cập nhật giá trị cuối

                payments_data.append({
                    'kind': p.loan_payment_kind or 'other',
                    'date': pay_date,
                    'date_from': getattr(p, 'date_from', False),
                    'date_to': getattr(p, 'date_to', False),
                    'interest_days': getattr(p, 'interest_days', 0) or 0,
                    'total': p.total or 0.0,
                    'interest_expected': interest_due,
                    'loan_balance': remaining_principal,
                    'loan_interest_outstanding': remaining_interest,
                    'currency': currency,
                })

            lines.append({
                'loan': loan,
                'currency': currency,
                'payments': payments_data,
                # các ô tổng hiển thị ngay hàng với STT của khoản vay
                'sum_total_paid': sum_total_paid,
                'sum_interest_expected': sum_interest_expected,
                'sum_interest_outstanding': sum_interest_outstanding,   # <-- dùng ô “Lãi còn nợ”
                'final_principal_balance': final_principal_balance,     # ô “Nợ gốc” (giá trị cuối)
            })

        return {
            'doc_ids': [],
            'doc_model': 'company.loan',
            'res_company': self.env.company,
            'user_id': self.env.user,
            'datetime': datetime,
            'lender': self.env['res.partner'].browse(lender_id),
            'lines': lines,
        }
