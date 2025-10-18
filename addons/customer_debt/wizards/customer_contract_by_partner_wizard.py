# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CustomerContractByPartnerWizard(models.TransientModel):
    _name = 'customer.contract.by.partner.wizard'
    _description = 'Wizard: Chọn khách hàng để xem báo cáo'

    partner_id = fields.Many2one(
        'res.partner',
        string="Khách hàng",
        domain=[('customer_rank', '>', 0), ('parent_id', '=', False)],
        required=True,
    )

    def action_print(self):
        self.ensure_one()
        action = self.env.ref('customer_debt.customer_contract_by_partner_report_action_html')
        return action.report_action(self.partner_id.id)


