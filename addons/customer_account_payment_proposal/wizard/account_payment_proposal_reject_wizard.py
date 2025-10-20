from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountPaymentProposalRejectWizard(models.TransientModel):
    _name = "account.payment.proposal.reject.wizard"
    _description = "Lý do từ chối giải chi"

    reason = fields.Text(string="Lý do từ chối", required=True)
    proposal_id = fields.Many2one("account.payment.proposal", string="Giấy đề nghị", required=True)

    def action_confirm_reject(self):
        self.ensure_one()
        proposal = self.proposal_id
        if not proposal:
            raise UserError(_("Không xác định được phiếu giải chi."))

        proposal.state = "rejected"

        # Ghi vào chatter
        proposal.message_post(
            body=f"❌ Phiếu giải chi đã bị từ chối.<br/><b>Lý do:</b> {self.reason}",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=[proposal.user_id.partner_id.id] if proposal.user_id.partner_id else [],
        )
