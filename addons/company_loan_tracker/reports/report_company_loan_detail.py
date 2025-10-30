# -*- coding: utf-8 -*-
from odoo import models, api, fields
import datetime


class ReportCompanyLoanDetail(models.AbstractModel):
    _name = 'report.company_loan_tracker.report_company_loan_detail_view'
    _description = 'Báo cáo chi tiết khoản vay theo bên cho vay'

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        lender_id = data.get('lender_id')

        Loan = self.env['company.loan']
        Payment = self.env['account.payment.request']

        loans = Loan.search([('lender_id', '=', lender_id)], order="name asc")
        loan_ids = loans.ids or [0]

        payments = Payment.search(
            [('loan_id', 'in', loan_ids)],
            order="loan_id, date_payment asc, create_date asc"
        )

        grouped = {}
        for p in payments:
            grouped.setdefault(p.loan_id.id, []).append(p)

        lines = []
        for loan in loans:
            pay_list = grouped.get(loan.id, [])
            currency = loan.currency_id or self.env.company.currency_id
            remaining_principal = loan.amount or 0.0

            payments_data = []
            sum_total_paid = 0.0
            sum_interest_expected = 0.0
            sum_interest_outstanding = 0.0
            final_principal_balance = remaining_principal

            # nếu có phiếu chi
            if pay_list:
                for p in pay_list:
                    pay_date = p.date_payment or (p.create_date and p.create_date.date())

                    if p.loan_payment_kind == 'principal':
                        remaining_principal -= (p.total or 0.0)
                        remaining_principal = max(remaining_principal, 0.0)

                    interest_due = getattr(p, 'interest_expected', 0.0) or 0.0
                    interest_paid = p.total if p.loan_payment_kind == 'interest' else 0.0
                    remaining_interest = max(interest_due - interest_paid, 0.0)

                    sum_total_paid += (p.total or 0.0)
                    sum_interest_expected += interest_due
                    sum_interest_outstanding += remaining_interest
                    final_principal_balance = remaining_principal

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
            else:
                # nếu chưa có phiếu chi => vẫn hiển thị 1 dòng tổng
                payments_data = []

            # thêm dòng vào báo cáo
            lines.append({
                'loan': loan,
                'currency': currency,
                'payments': payments_data,
                'sum_total_paid': sum_total_paid,
                'sum_interest_expected': sum_interest_expected,
                'sum_interest_outstanding': sum_interest_outstanding,
                'final_principal_balance': final_principal_balance,
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
