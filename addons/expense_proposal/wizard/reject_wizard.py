from odoo import models, fields

class ExpenseProposalRejectWizard(models.TransientModel):
    _name = 'expense.proposal.reject.wizard'
    _description = 'Lý do từ chối đề xuất chi phí'

    reason = fields.Text(string="Lý do từ chối", required=True)

    def action_confirm_reject(self):
        active_id = self.env.context.get('active_id')
        if active_id:
            proposal = self.env['expense.proposal'].browse(active_id)
            proposal.write({
                'state': 'rejected',
            })
            # Ghi vào chatter
            proposal.message_post(body=f"Phiếu bị từ chối với lý do: <br/>{self.reason}")
        return {'type': 'ir.actions.act_window_close'}
