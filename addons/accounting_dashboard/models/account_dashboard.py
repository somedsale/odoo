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
        PaymentProposal = self.env['account.payment.proposal']

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
                ('status_expense', 'in', ['paid'])
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
        proposal_count = Proposal.sudo().search_count([
            ('state', 'in', ['reviewed_accounting', 'waiting_accounting_paid']),
            ('date_proposal', '>=', dt_from),
            ('date_proposal', '<=', dt_to),
        ])

        # ----------------------------
        # Giải chi kế toán cần xử lý
        # ----------------------------
        payment_proposal_count = PaymentProposal.sudo().search_count([
            ('state', 'in', ['dept_approved', 'director_approved']),
            ('date_request', '>=', dt_from),
            ('date_request', '<=', dt_to),
        ])
        daily_cash_flow = []
        day_cursor = dt_from
        while day_cursor <= dt_to:
            # Tổng tiền thu trong ngày
            receipts_day = sum(r.get('amount') or 0.0 for r in Receipt.search_read(
                [('date', '=', day_cursor), ('state', 'in', ['posted'])],
                ['amount']
            ))
            # Tổng tiền chi trong ngày
            payments_day = sum(r.get('total') or 0.0 for r in PayReq.search_read(
                [('date_payment', '=', day_cursor),
                 ('state', 'in', ['approved', 'post', 'paid', 'done'])],
                ['total']
            ))

            daily_cash_flow.append({
                'date': day_cursor.isoformat(),
                'cash_in': receipts_day,
                'cash_out': payments_day,
            })
            day_cursor += timedelta(days=1)
        SupplierInvoice = self.env['supplier.invoice']
        supplier_invoices = SupplierInvoice.search_read(
            [
                ('date', '>=', dt_from),
                ('date', '<=', dt_to),
            ],
            ['id', 'name', 'partner_id', 'amount', 'date','due_date'],
            order='date desc'
        )
        total_supplier_invoice = sum(inv.get('amount') or 0.0 for inv in supplier_invoices)

        # ----------------------------
        # Hóa đơn đầu ra (Customer Invoice)
        # ----------------------------
        CustomerInvoice = self.env['customer.invoice']
        customer_invoices = CustomerInvoice.search_read(
            [
                ('date', '>=', dt_from),
                ('date', '<=', dt_to),
            ],
            ['id', 'name', 'partner_id', 'amount_total', 'date'],
            order='date desc'
        )
        total_customer_invoice = sum(inv.get('amount_total') or 0.0 for inv in customer_invoices)
        # ----------------------------
        # Kết quả trả về
        # ----------------------------
        return {
            'cash_in': float(cash_in),
            'cash_out': float(cash_out),
            'net_cash': float(net_cash),
            'employee_advance_remain_total': float(total_employee_remain),
            'employees_with_remain': employees_with_remain,
            'proposal_pending_count': proposal_count,
            'payment_proposals_pending_count': payment_proposal_count,
            'daily_cash_flow': daily_cash_flow,
            'supplier_invoices': supplier_invoices,
            'customer_invoices': customer_invoices,
            'total_supplier_invoice': float(total_supplier_invoice),
            'total_customer_invoice': float(total_customer_invoice),
            'period': {
                'date_from': dt_from.isoformat(),
                'date_to': dt_to.isoformat(),
            },
        }
