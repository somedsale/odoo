# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CompanyLoanDetailWizard(models.TransientModel):
    _name = 'company.loan.detail.wizard'
    _description = 'Tham số báo cáo chi tiết khoản vay theo bên cho vay'

    lender_id = fields.Many2one(
        'res.partner', string='Người cho vay', required=True,
        domain=[('is_lender', '=', True)]
    )
    date_from = fields.Date(string='Từ ngày')
    date_to   = fields.Date(string='Đến ngày')
    def action_print_detail(self):
        self.ensure_one()
        data = {
            'lender_id': self.lender_id.id,
            'date_from': self.date_from and self.date_from.isoformat() or False,
            'date_to': self.date_to and self.date_to.isoformat() or False,
        }
        return self.env.ref('company_loan_tracker.action_company_loan_detail_report').report_action(None, data=data)
