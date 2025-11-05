# -*- coding: utf-8 -*-
from odoo import models, api, fields
from datetime import datetime, timedelta

class AccountingDashboard(models.AbstractModel):
    _name = "wt.account.dashboard"
    _description = "Accounting Dashboard - Simple Totals"

    @api.model
    def get_dashboard_data(self, date_from=None, date_to=None):
        now = fields.Date.context_today(self)

        # ----------------------------
        # Chuẩn hoá khoảng ngày
        # ----------------------------
        if date_to:
            try:
                dt_to = datetime.fromisoformat(str(date_to)[:19]).date()
            except Exception:
                dt_to = now
        else:
            dt_to = now

        if date_from:
            try:
                dt_from = datetime.fromisoformat(str(date_from)[:19]).date()
            except Exception:
                dt_from = dt_to - timedelta(days=30)
        else:
            dt_from = dt_to - timedelta(days=30)

        Receipt = self.env['account.receipt']
        PayReq  = self.env['account.payment.request']
        EmpAdv  = self.env['account.employee.advance']
        Proposal = self.env['proposal.sheet']

        # ----------------------------
        # Tiền thu
        # ----------------------------
        cash_in = sum(r.get('amount') or 0.0 for r in Receipt.search_read(
            [
                ('date', '>=', dt_from),
                ('date', '<=', dt_to),
                ('state', 'in', ['posted'])
            ],
            ['amount']
        ))

        # ----------------------------
        # Tiền chi
        # ----------------------------
        cash_out = sum(r.get('total') or 0.0 for r in PayReq.search_read(
            [
                ('date_payment', '>=', dt_from),
                ('date_payment', '<=', dt_to),
                ('state', 'in', ['approved', 'post', 'paid', 'done'])
            ],
            ['total']
        ))

        net_cash = float(cash_in) - float(cash_out)

        # ----------------------------
        # Dư tạm ứng
        # ----------------------------
        positive_advances = EmpAdv.search([('remain_total', '>', 0)], order="remain_total desc")
        total_employee_remain = sum(positive_advances.mapped('remain_total'))

        employees_with_remain = [
            {
                'employee_id': adv.employee_id.id,
                'employee_name': adv.employee_id.name,
                'department_name': adv.department_id.name or '',
                'remain_total': adv.remain_total,
            }
            for adv in positive_advances
        ]

        # ----------------------------
        # Phiếu đề xuất cần xử lý
        # ----------------------------
        proposals = Proposal.sudo().search_read(
            [
                ('state', 'in', ['reviewed_accounting', 'waiting_accounting_paid']),
                ('create_date', '>=', dt_from),
                ('create_date', '<=', dt_to),
            ],
            ['id', 'name', 'project_id', 'requested_by', 'amount_total', 'state', 'create_date'],
            limit=10,
            order='create_date desc'
        )

        # ----------------------------
        # Kết quả trả về
        # ----------------------------
        return {
            'cash_in': float(cash_in),
            'cash_out': float(cash_out),
            'net_cash': float(net_cash),
            'employee_advance_remain_total': float(total_employee_remain),
            'employees_with_remain': employees_with_remain,
            'proposal_pending': proposals,   # ✅ thêm key mới cho dashboard JS
            'period': {
                'date_from': dt_from.isoformat(),
                'date_to': dt_to.isoformat(),
            },
        }
