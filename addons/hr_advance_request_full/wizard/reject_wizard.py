# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class SomedAdvanceRejectWizard(models.TransientModel):
    _name = 'somed.advance.reject.wizard'
    _description = 'Wizard từ chối phiếu tạm ứng'

    advance_id = fields.Many2one('somed.advance.request', string='Phiếu tạm ứng', required=True, readonly=True)
    reason = fields.Text(string='Lý do từ chối', required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        if not self.reason or not self.reason.strip():
            raise UserError(_('Vui lòng nhập lý do từ chối.'))
        self.advance_id.action_reject_with_reason(self.reason.strip())
        return {'type': 'ir.actions.act_window_close'}
