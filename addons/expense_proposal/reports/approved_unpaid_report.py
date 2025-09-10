# -*- coding: utf-8 -*-
from odoo import api, fields, models
from datetime import date  # <— thêm

class ReportApprovedUnpaid(models.AbstractModel):
    _name = 'report.expense_proposal.report_approved_unpaid'
    _description = 'QWeb Report: Approved but Unpaid Expense Lines'

    @api.model
    def _get_report_values(self, docids, data=None):
        prs = self.env['account.payment.request'].search([
            ('status_expense', '!=', 'paid'),
            ('total', '>', 0.0)
        ])

        total_cash = {'employee': 0.0, 'office': 0.0, 'project': 0.0}
        total_bank = {'employee': 0.0, 'office': 0.0, 'project': 0.0}

        line_items_employee, line_items_office, line_items_project = [], [], []

        def _push_line(ap, bucket):
            cat = ap.expense_category_id
            payload = {
                'date': ap.scheduled_date,
                'note': (getattr(ap, 'note', '') or '') if hasattr(ap, 'note') else '',
                'total': ap.total or 0.0,
                'payment_type': ap.payment_type,               # 'cash' | 'bank'
                'cost_classification': ap.cost_classification,
                'expense_category_id': cat or False,
                'category_name': (getattr(cat, 'complete_name', False) or cat.display_name) if cat else '',  # <— khóa sắp xếp
                'project_id': ap.project_id or False,
                'project': ap.project_id.display_name if ap.project_id else '',  # (nếu cần sort phụ)
            }
            bucket.append(payload)

        for ap in prs:
            cls = ap.cost_classification or 'office'
            amt = ap.total or 0.0

            if cls == 'employee':
                _push_line(ap, line_items_employee)
            elif cls == 'office':
                _push_line(ap, line_items_office)
            else:
                _push_line(ap, line_items_project)

            if ap.payment_type == 'cash':
                total_cash[cls] = (total_cash.get(cls, 0.0) or 0.0) + amt
            elif ap.payment_type == 'bank':
                total_bank[cls] = (total_bank.get(cls, 0.0) or 0.0) + amt

        # 👉 SẮP XẾP: khoản mục -> dự án -> ngày
        def _sort_lines(lines):
            return sorted(
                lines,
                key=lambda l: (
                    (l.get('category_name') or '').lower(),
                    (l.get('project') or '').lower(),
                    l.get('date') or date.min
                )
            )

        line_items_employee = _sort_lines(line_items_employee)
        line_items_office   = _sort_lines(line_items_office)
        line_items_project  = _sort_lines(line_items_project)

        cash_total_amount = sum(total_cash.values())
        bank_total_amount = sum(total_bank.values())

        lists = [{
            'total_cash_employee': total_cash['employee'],
            'total_cash_office': total_cash['office'],
            'total_cash_project': total_cash['project'],
            'total_bank_employee': total_bank['employee'],
            'total_bank_office': total_bank['office'],
            'total_bank_project': total_bank['project'],
            'line_items_employee': line_items_employee,
            'line_items_office': line_items_office,
            'line_items_project': line_items_project,
        }]

        return {
            'doc_model': 'account.payment.request',
            'docs': prs,
            'lists': lists,
            'cash_total_amount': cash_total_amount,
            'bank_total_amount': bank_total_amount,
            'total': cash_total_amount + bank_total_amount,
            'today': fields.Date.context_today(self),
            'company': self.env.company,
            'is_pdf': self.env.context.get('report_type') in ('qweb-pdf','pdf','pdf_searchable'),

        }
