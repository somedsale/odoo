from odoo import models, fields

class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    purchase_id = fields.Many2one(
        'purchase.order',
        string="Đơn mua hàng",
        index=True,
        ondelete='set null',
    )
    task_id = fields.Many2one('project.task', string="Nhiệm vụ", index=True)
    payment_kind = fields.Selection([
        ('advance', 'Tạm ứng'),
        ('full', 'Thanh toán toàn bộ'),
    ], string="Kiểu thanh toán", default='advance', required=True)
