from odoo import fields, models, api

class SupplierDebtSummary(models.Model):
    _name = 'supplier.debt.summary'
    _description = 'Tổng hợp công nợ phải trả nhà cung cấp'

    supplier_id = fields.Many2one('res.partner', string='Nhà cung cấp', required=True, domain=[('supplier_rank', '>', 0)])
    project_id = fields.Many2one('project.project', string='Dự án')
    purchase_contract_id = fields.Many2one('purchase.contract', string='Hợp đồng', store=True)  # Hợp đồng liên quan đến công nợ
    purchase_invoice_id = fields.Many2one('purchase.invoice', string='Hóa đơn mua', help='Hóa đơn liên quan đến hợp đồng mua')
    paid_amount = fields.Monetary(string='Số tiền thanh toán',compute='_compute_paid_amount', currency_field='currency_id', readonly=True)
    due_amount = fields.Monetary(string='Số tiền còn nợ', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)