from odoo import fields, models, api

class SupplierDebtSummary(models.Model):
    _name = 'supplier.debt.summary'
    _description = 'Tổng hợp công nợ phải trả nhà cung cấp'
    supplier_id = fields.Many2one(
        'res.partner',
        string='Nhà cung cấp',
        required=True,
        domain=[('supplier_rank', '>', 0)]
    )
    # description = fields.Text(string='Diễn giải')
    total_contract_value = fields.Monetary(
        string='Tổng giá trị hợp đồng',
        compute='_compute_contract_summary',
        currency_field='currency_id',
        help='Tổng giá trị của tất cả các hợp đồng mua liên quan đến nhà cung cấp này.'
    )
    total_invoice_amount = fields.Monetary(
        string='Tổng giá trị hóa đơn',
        compute='_compute_contract_summary',
        currency_field='currency_id',
        help='Tổng giá trị của tất cả các hóa đơn liên quan đến các hợp đồng của nhà cung cấp này.'
    )
    total_due_amount = fields.Monetary(
        string='Tổng số tiền còn nợ',
        compute='_compute_contract_summary',
        currency_field='currency_id',
        help='Tổng số tiền còn nợ từ tất cả các hợp đồng của nhà cung cấp này (tổng hóa đơn - tổng đã thanh toán).'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id,
        readonly=True
    )
    purchase_contract_ids = fields.One2many(
        'purchase.contract',
        'supplier_debt_summary_id',
        string='Hợp đồng mua',
        help='Hợp đồng mua liên quan đến nhà cung cấp.'
    )
    @api.depends('supplier_id')
    def _compute_contract_summary(self):
        for record in self:
            record.total_contract_value = 0
            record.total_invoice_amount = 0
            record.total_due_amount = 0
            if record.supplier_id and record.supplier_id.supplier_rank > 0:
                contracts = self.env['purchase.contract'].search([('supplier_id', '=', record.supplier_id.id)])
                if contracts:
                    record.total_contract_value = sum(contracts.mapped('value'))
                    record.total_invoice_amount = sum(contracts.mapped('invoice_amount'))
                    record.total_due_amount = sum(contracts.mapped('due_amount'))