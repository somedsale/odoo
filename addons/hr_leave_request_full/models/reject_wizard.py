# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import ValidationError


class SomedLeaveRejectWizard(models.TransientModel):
    _name = 'somed.leave.reject.wizard'
    _description = 'Wizard từ chối đơn nghỉ phép'

    request_id = fields.Many2one('somed.leave.request', string='Đơn nghỉ phép', required=True)
    reason = fields.Text(string='Lý do từ chối', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('Vui lòng nhập lý do từ chối.'))
        self.request_id.action_reject_with_reason(self.reason.strip())
        return {'type': 'ir.actions.act_window_close'}
