from odoo import models, fields, api

class SaleContract(models.Model):
    _name = 'sale.contract'
    _description = 'Sale Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    name_contact = fields.Char(string='Contact Name', required=True)
    num_contract = fields.Char(string='Contract Number', required=True)
    
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', domain=[('state', 'in', ['sale', 'done'])])
    date_contract = fields.Date(string='Contract Date', default=fields.Date.today)
    terms_conditions = fields.Text(string='Terms and Conditions')
    contract_lines = fields.One2many('sale.contract.line', 'contract_id', string='Contract Lines')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft')
    amount_total = fields.Float(string='Total', compute='_compute_amount_total', store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.contract') or 'New'
        return super(SaleContract, self).create(vals)

    @api.depends('contract_lines.price_subtotal')
    def _compute_amount_total(self):
        for contract in self:
            contract.amount_total = sum(line.price_subtotal for line in contract.contract_lines)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_create_from_sale_order(self):
        if self.sale_order_id:
            self.contract_lines = [(5, 0, 0)]  # Clear existing lines
            for line in self.sale_order_id.order_line:
                self.contract_lines.create({
                    'contract_id': self.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                })

class SaleContractLine(models.Model):
    _name = 'sale.contract.line'
    _description = 'Sale Contract Line'

    contract_id = fields.Many2one('sale.contract', string='Contract')
    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(string='Subtotal', compute='_compute_price_subtotal', store=True)

    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit