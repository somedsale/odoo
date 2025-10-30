# -*- coding: utf-8 -*-
from odoo import models, api
import datetime  # để truyền vào template (dùng today().day,...)
from collections import defaultdict

class ReportCompanyLoan(models.AbstractModel):
    _name = 'report.company_loan_tracker.report_company_loan_view'
    _description = 'Báo cáo Tổng Hợp Khoản Vay Công Ty'

    @api.model
    def _get_report_values(self, docids, data=None):
        Loan = self.env['company.loan']

        # Lấy danh sách khoản vay để in
        if docids and docids != [0]:
            loans = Loan.browse(docids)
        else:
            loans = Loan.search([])

        # map selection loan_type -> label
        selection_map = dict(Loan._fields['loan_type'].selection)
        # thứ tự hiển thị các nhóm
        order_key = ['short_term', 'medium_term', 'personal']

        grouped_loans = []

        for lt in order_key:
            # tất cả khoản vay thuộc loại này
            lt_records = loans.filtered(lambda l: l.loan_type == lt)
            if not lt_records:
                continue

            # subtotal cho cả loại vay này
            subtotal_amount = sum(lt_records.mapped('amount') or [0.0])
            subtotal_principal_paid = sum(lt_records.mapped('total_paid') or [0.0])
            subtotal_interest_paid = sum(lt_records.mapped('total_interest_paid') or [0.0])
            subtotal_principal_balance = sum(lt_records.mapped('balance') or [0.0])
            subtotal_interest_outstanding = sum(lt_records.mapped('interest_outstanding') or [0.0])

            # ---------- GỘP THEO lender_id BÊN TRONG LOẠI VAY ----------
            # dict tạm: lender_id -> list các record khoản vay cụ thể
            lender_bucket = defaultdict(list)
            for rec in lt_records:
                lender_bucket[rec.lender_id.id].append(rec)

            aggregated_rows = []
            for lender_id, rec_list in lender_bucket.items():
                # tổng cho 1 lender trong loại vay này
                amount_sum = sum(r.amount or 0.0 for r in rec_list)
                principal_paid_sum = sum(r.total_paid or 0.0 for r in rec_list)
                interest_paid_sum = sum(r.total_interest_paid or 0.0 for r in rec_list)
                principal_balance_sum = sum(r.balance or 0.0 for r in rec_list)
                interest_outstanding_sum = sum(r.interest_outstanding or 0.0 for r in rec_list)

                # xử lý lãi suất hiển thị:
                # - nếu tất cả các khoản của lender này cùng 1 lãi suất (và !=0) => hiện %
                # - nếu khác nhau hoặc có cả 0 / None => để "-"
                rates = set([round(r.interest_rate or 0.0, 4) for r in rec_list])
                if len(rates) == 1 and list(rates)[0] not in (0.0, 0):
                    interest_rate_display = f"{list(rates)[0]} %"
                else:
                    interest_rate_display = "-"

                # xử lý interest_note (Ngày trả lãi/gốc):
                # nếu tất cả các khoản ghi cùng 1 note => dùng note đó
                # nếu khác nhau => "-"
                notes = set([ (r.interest_note or "").strip() for r in rec_list if (r.interest_note or "").strip() ])
                if len(notes) == 1:
                    interest_note_display = list(notes)[0]
                else:
                    interest_note_display = "-"

                aggregated_rows.append({
                    'lender_name': rec_list[0].lender_id.name,
                    'amount_sum': amount_sum,
                    'interest_rate_display': interest_rate_display,
                    'principal_paid_sum': principal_paid_sum,
                    'interest_paid_sum': interest_paid_sum,
                    'principal_balance_sum': principal_balance_sum,
                    'interest_outstanding_sum': interest_outstanding_sum,
                    'interest_note_display': interest_note_display,
                })

            # push vào grouped_loans
            grouped_loans.append({
                'loan_type': lt,
                'loan_type_label': selection_map.get(lt, lt),
                'subtotal': {
                    'amount': subtotal_amount,
                    'principal_paid': subtotal_principal_paid,
                    'interest_paid': subtotal_interest_paid,
                    'principal_balance': subtotal_principal_balance,
                    'interest_outstanding': subtotal_interest_outstanding,
                },
                # đây là list đã gộp theo lender
                'aggregated_rows': aggregated_rows,
            })

        # ---------- GRAND TOTAL CHO TẤT CẢ ----------
        grand_total = {
            'amount': sum(loans.mapped('amount') or [0.0]),
            'principal_paid': sum(loans.mapped('total_paid') or [0.0]),
            'interest_paid': sum(loans.mapped('total_interest_paid') or [0.0]),
            'principal_balance': sum(loans.mapped('balance') or [0.0]),
            'interest_outstanding': sum(loans.mapped('interest_outstanding') or [0.0]),
        }

        return {
            'doc_ids': loans.ids,
            'doc_model': 'company.loan',
            'res_company': self.env.company,
            'user_id': self.env.user,
            'datetime': datetime,
            'grand_total': grand_total,
            'grouped_loans': grouped_loans,
        }
