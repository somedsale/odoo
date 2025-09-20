from odoo import models, fields, _
class SupplierInvoice(models.Model):
    _inherit = 'supplier.invoice'

    purchase_id = fields.Many2one('purchase.order', string="Đơn mua hàng", index=True)
