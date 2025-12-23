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
        data = data or {}
        month = int(data.get('month'))
        year = int(data.get('year'))
        start_date = date(year, month, 1)
        end_date = start_date + relativedelta(months=1, days=-1)

        # ==============================
        # 🔹 Doanh thu (GIỮ NGUYÊN)
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
        # 🔹 Chi phí (A/B GÁN CỨNG theo expense_bucket)
        # ==============================

        FIXED_A = [
            ("rent_office_factory", "Chi phí thuê văn phòng + xưởng"),
        ]

        FIXED_B_COMPANY = [
            ("loan_principal", "Trả gốc vay (Ngân hàng + cá nhân)"),
            ("loan_interest", "Lãi vay (Ngân hàng, Cá nhân)"),
            ("bank_fee", "Phí ngân hàng (CK, Phí số dư, mua SEC,...)"),
            ("salary_board", "Chi phí lương ban Giám Đốc"),
            ("salary_sales", "Chi phí lương Kinh Doanh"),
            ("salary_accounting", "Chi phí lương Kế Toán"),
            ("salary_planning_tech_production", "Chi phí lương bộ phận kế hoạch kỹ thuật và sản xuất"),
            ("insurance_215", "Chi phí BHXH, BHYT, BHTN 21,5%"),
            ("electric_water", "Chi phí điện, Nước sinh hoạt"),
            ("phone_fee", "Chi phí Cước điện thoại (di động, cố định, số hotline...)"),
            ("internet_fee", "Cước Internet văn phòng"),
            ("stationery_hygiene_shipping", "Văn phòng phẩm + vật dụng vệ sinh + cước vận chuyển"),
            ("garbage_fee", "Chi phí đổ rác"),
            ("reception", "Chi phí Tiếp khách"),
            ("drinking_water", "Chi phí nước uống bình nhân viên"),
            ("badminton", "Chi phí cầu lông (đặt sân, mua cầu..)"),
            ("worship", "Chi phí cúng (mùng 1,15, ....)"),
        ]

        A_KEYS = [k for k, _ in FIXED_A]
        B_KEYS = [k for k, _ in FIXED_B_COMPANY]

        payments = self.env['account.payment.request'].search([
            ('date_payment', '>=', start_date),
            ('date_payment', '<=', end_date),
            ('state', 'in', ['post', 'done']),
        ])

        def _sum_fixed(records, keys):
            sums = {k: 0.0 for k in keys}
            unknown = 0.0
            for p in records:
                k = p.expense_bucket
                amt = p.total or 0.0
                if k in sums:
                    sums[k] += amt
                else:
                    unknown += amt
            return sums, unknown

        # ✅ A: CHỈ theo bucket rent_office_factory
        A_recs = payments.filtered(lambda x: x.expense_bucket in A_KEYS)
        A_SUMS, A_UNKNOWN = _sum_fixed(A_recs, A_KEYS)

        # ✅ B/a: theo 17 bucket còn lại
        B_recs = payments.filtered(lambda x: x.expense_bucket in B_KEYS)
        B_SUMS, B_UNKNOWN = _sum_fixed(B_recs, B_KEYS)

        # b. Chi phí công trình (GIỮ NGUYÊN)
        project_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'project'):
            key = p.project_id.name or _('(Không có dự án)')
            project_costs[key] += (p.total or 0.0)

        # C. Biến phí không thường xuyên (GIỮ NGUYÊN)
        irregular_costs = defaultdict(float)
        for p in payments.filtered(lambda x: x.cost_classification == 'irregular_expenses'):
            key = p.expense_category_id.name or _('(Không có khoản mục)')
            irregular_costs[key] += (p.total or 0.0)

        # Luôn đủ dòng
        A_LINES = [{'key': k, 'name': label, 'expense': A_SUMS.get(k, 0.0)} for k, label in FIXED_A]
        B_LINES = [{'key': k, 'name': label, 'expense': B_SUMS.get(k, 0.0)} for k, label in FIXED_B_COMPANY]

        # Nếu muốn bắt lỗi phiếu chi chọn bucket ngoài list / không chọn bucket thì bật dòng dưới
        # if A_UNKNOWN:
        #     A_LINES.append({'key': 'unclassified', 'name': 'Chưa phân loại (A)', 'expense': A_UNKNOWN})
        # if B_UNKNOWN:
        #     B_LINES.append({'key': 'unclassified', 'name': 'Chưa phân loại (B/a)', 'expense': B_UNKNOWN})

        expense_data = [
            {
                'type_label': 'A. TỔNG ĐỊNH PHÍ',
                'lines': A_LINES,
                'subtotal': sum(x['expense'] for x in A_LINES),
            },
            {
                'type_label': 'B. TỔNG BIẾN PHÍ THƯỜNG XUYÊN',
                'subgroups': [
                    {
                        'sub_label': 'a. Chi phí công ty',
                        'lines': B_LINES,
                        'subtotal': sum(x['expense'] for x in B_LINES),
                    },
                    {
                        'sub_label': 'b. Chi phí công trình',
                        'lines': [{'name': k, 'expense': v} for k, v in project_costs.items()],
                        'subtotal': sum(project_costs.values()),
                    },
                ],
                'subtotal': sum(x['expense'] for x in B_LINES) + sum(project_costs.values()),
            },
            {
                'type_label': 'C. TỔNG BIẾN PHÍ KHÔNG THƯỜNG XUYÊN',
                'lines': [{'name': k, 'expense': v} for k, v in irregular_costs.items()],
                'subtotal': sum(irregular_costs.values()),
            },
        ]

        # ==============================
        # 🔹 Tổng hợp cuối (GIỮ NGUYÊN)
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
