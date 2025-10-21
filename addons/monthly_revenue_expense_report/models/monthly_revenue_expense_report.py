# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import date
from dateutil.relativedelta import relativedelta
from collections import defaultdict

class MonthlyRevenueExpenseReport(models.TransientModel):
    _name = 'monthly.revenue.expense.report'
    _description = 'Báo cáo doanh thu - chi phí hàng tháng'

    month = fields.Selection(
        [(str(m), f'Tháng {m}') for m in range(1, 13)],
        string='Tháng', required=True, default=lambda self: str(date.today().month)
    )
    year = fields.Integer(
        string='Năm', required=True, default=lambda self: date.today().year
    )

    def action_view_report(self):
        self.ensure_one()
        data = {'month': self.month, 'year': self.year}
        return self.env.ref(
            'monthly_revenue_expense_report.report_monthly_revenue_expense_action_html'
        ).report_action(self, data=data)


class AccountReceiptReport(models.AbstractModel):
    _name = 'report.monthly_revenue_expense_report.report_template'
    _description = 'Render báo cáo doanh thu - chi phí hàng tháng'

    @api.model
    def _get_report_values(self, docids, data=None):
        month = int(data.get('month'))
        year = int(data.get('year'))
        start_date = date(year, month, 1)
        end_date = start_date + relativedelta(months=1, days=-1)

        # ==============================
        # 🔹 Doanh thu
        # ==============================
        receipts = self.env['account.receipt'].search([
            ('date', '>=', start_date),
            ('date', '<=', end_date),
            ('state', '=', 'posted'),
        ])

        rev_grouped = defaultdict(lambda: defaultdict(float))
        for r in receipts:
            tkey = r.type_revenue or 'unknown'
            if tkey in ('done_revenue', 'advance'):
                if not r.project_id:
                    continue
                key_name = r.project_id.name
            elif tkey in ('loan', 'other'):
                key_name = r.project_id.name if r.project_id else (r.note or _('(Không có nội dung)'))
            else:
                continue
            rev_grouped[tkey][key_name] += r.amount

        rev_order = [
            ('done_revenue', 'A. Doanh thu đã thực hiện'),
            ('advance', 'B. Doanh thu chưa thực hiện (Tạm ứng)'),
            ('other', 'C. Các khoản thu khác'),
            ('loan', 'D. Các khoản vay'),
        ]

        revenue_data = []
        for key, label in rev_order:
            project_lines = rev_grouped.get(key, {})
            total = sum(project_lines.values())
            revenue_data.append({
                'type_key': key,
                'type_label': label,
                'projects': [{'name': k, 'revenue': v} for k, v in project_lines.items()],
                'subtotal': total,
            })

        # ==============================
        # 🔹 Chi phí
        # ==============================
        payments = self.env['account.payment.request'].search([
            ('date_payment', '>=', start_date),
            ('date_payment', '<=', end_date),
            ('state', 'in', ['post', 'done']),
        ])

        # ---- A. TỔNG ĐỊNH PHÍ ----
        fixed_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'fixed_cost'):
            key = p.expense_category_id.name or _('(Không có khoản mục)')
            fixed_costs[key] += p.total

        # ---- B. TỔNG BIẾN PHÍ THƯỜNG XUYÊN ----
        # a. Chi phí công ty
        office_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'office'):
            key = p.expense_category_id.name or _('(Không có khoản mục)')
            office_costs[key] += p.total

        # b. Chi phí công trình
        project_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'project'):
            key = p.project_id.name or _('(Không có dự án)')
            project_costs[key] += p.total

        # ---- C. TỔNG BIẾN PHÍ KHÔNG THƯỜNG XUYÊN ----
        irregular_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'irregular_expenses'):
            key = p.expense_category_id.name or _('(Không có khoản mục)')
            irregular_costs[key] += p.total

        # Gom thành cấu trúc hiển thị
        expense_data = [
            {
                'type_label': 'A. TỔNG ĐỊNH PHÍ',
                'lines': [{'name': k, 'expense': v} for k, v in fixed_costs.items()],
                'subtotal': sum(fixed_costs.values()),
            },
            {
                'type_label': 'B. TỔNG BIẾN PHÍ THƯỜNG XUYÊN',
                'subgroups': [
                    {
                        'sub_label': 'a. Chi phí công ty',
                        'lines': [{'name': k, 'expense': v} for k, v in office_costs.items()],
                        'subtotal': sum(office_costs.values()),
                    },
                    {
                        'sub_label': 'b. Chi phí công trình',
                        'lines': [{'name': k, 'expense': v} for k, v in project_costs.items()],
                        'subtotal': sum(project_costs.values()),
                    },
                ],
                'subtotal': sum(office_costs.values()) + sum(project_costs.values()),
            },
            {
                'type_label': 'C. TỔNG BIẾN PHÍ KHÔNG THƯỜNG XUYÊN',
                'lines': [{'name': k, 'expense': v} for k, v in irregular_costs.items()],
                'subtotal': sum(irregular_costs.values()),
            },
        ]

        # ==============================
        # 🔹 Tổng hợp cuối
        # ==============================
        total_revenue = sum(r.amount for r in receipts if r.type_revenue not in ('explain',))
        total_expense = sum(p.total for p in payments)
        net_profit = total_revenue - total_expense

        return {
            'doc_ids': docids,
            'doc_model': 'account.receipt',
            'month': month,
            'year': year,
            'start_date': start_date,
            'end_date': end_date,
            'revenue_data': revenue_data,
            'expense_data': expense_data,
            'total_revenue': total_revenue,
            'total_expense': total_expense,
            'net_profit': net_profit,
        }