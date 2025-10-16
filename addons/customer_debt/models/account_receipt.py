# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountReceiptInherit(models.Model):
    _inherit = 'account.receipt'


    contract_id = fields.Many2one(
        'customer.contract',
        string='Hợp đồng khách hàng',
        ondelete='set null'
    )
    invoice_id = fields.Many2one(
        'customer.invoice',
        string='Hóa đơn khách hàng',
        ondelete='set null'
    )
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        """Tự động gán khách hàng & dự án khi chọn hợp đồng"""
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.project_id = self.contract_id.project_id
