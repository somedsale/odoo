from odoo import models, fields, api
from odoo.exceptions import UserError


class ProposalRejectWizard(models.TransientModel):
    _name = 'proposal.reject.wizard'
    _description = 'Wizard Từ Chối Phiếu Đề Xuất'

    reason = fields.Text(string="Lý do từ chối", required=True)

    def action_confirm_reject(self):
        active_id = self.env.context.get('active_id')
        proposal = self.env['proposal.sheet'].browse(active_id)
        if proposal:
            proposal.state = 'rejected'
            proposal.message_post(body=f'Phiếu đề xuất bị từ chối. Lý do: {self.reason}')
        return {'type': 'ir.actions.act_window_close','tag': 'reload'}
