from odoo import models, fields, api # type: ignore

class SaleContract(models.Model):
    _name = 'sale.contract'
    _description = 'Sale Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, default=lambda self: self.env['ir.sequence'].next_by_code('sale.contract'))
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    date_contract = fields.Date(string='Contract Date', default=fields.Date.today)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('signed', 'Signed'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', track_visibility='onchange')
    contract_line_ids = fields.One2many('sale.contract.line', 'contract_id', string='Contract Lines')
    amount_total = fields.Float(string='Total', compute='_compute_amount_total', store=True)
    note = fields.Text(string='Terms and Conditions')

    @api.depends('contract_line_ids.price_subtotal')
    def _compute_amount_total(self):
        for contract in self:
            contract.amount_total = sum(line.price_subtotal for line in contract.contract_line_ids)

    def action_send(self):
        self.state = 'sent'

    def action_sign(self):
        self.state = 'signed'

    def action_cancel(self):
        self.state = 'cancel'

class SaleContractLine(models.Model):
    _name = 'sale.contract.line'
    _description = 'Sale Contract Line'

    contract_id = fields.Many2one('sale.contract', string='Contract', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    name = fields.Text(string='Description', required=True)
    quantity = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(string='Subtotal', compute='_compute_price_subtotal', store=True)
    tax_id = fields.Many2many('account.tax', string='Taxes')

    @api.depends('quantity', 'price_unit', 'tax_id')
    def _compute_price_subtotal(self):
        for line in self:
            price = line.price_unit * line.quantity
            taxes = line.tax_id.compute_all(price, line.contract_id.currency_id, line.quantity, product=line.product_id, partner=line.contract_id.partner_id)
            line.price_subtotal = taxes['total_excluded']