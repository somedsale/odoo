from odoo import models, fields

class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    payment_proposal_id = fields.Many2one('account.payment.proposal', string="Đề nghị giải chi")
    employee_id = fields.Many2one(
        'hr.employee',
        string="Nhân viên",
        help="Nhân viên nhận tạm ứng hoặc người được thanh toán chi phí.",
    )
    is_advance = fields.Boolean(string="Tạm ứng", default=False)
    note_advance = fields.Text(string="Ghi chú")
