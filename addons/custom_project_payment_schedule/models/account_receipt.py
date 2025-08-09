# -*- coding: utf-8 -*-
from odoo import models, fields,api

class AccountReceiptInherit(models.Model):
    _inherit = 'account.receipt'

    schedule_id = fields.Many2one(
        'project.payment.schedule',
        string='Đợt thanh toán',
        ondelete='set null'
    )
    @api.onchange('schedule_id')
    def _onchange_schedule_id(self):
        if self.schedule_id:
            self.project_id = self.schedule_id.project_id
            self.partner_id = self.schedule_id.partner_id
