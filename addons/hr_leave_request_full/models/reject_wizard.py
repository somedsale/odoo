# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SomedLeaveRejectWizard(models.TransientModel):
    _name = 'somed.leave.reject.wizard'
    _description = 'Wizard từ chối đơn xin nghỉ phép'

    leave_request_id = fields.Many2one('somed.leave.request', string='Đơn xin nghỉ phép', required=True, readonly=True)
    reason = fields.Text(string='Lý do từ chối', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_('Vui lòng nhập lý do từ chối.'))
        self.leave_request_id.action_reject_with_reason(self.reason)
        return {'type': 'ir.actions.act_window_close'}
