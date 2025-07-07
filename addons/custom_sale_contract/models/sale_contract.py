from odoo import models, fields, api
from collections import defaultdict

class SaleContract(models.Model):
    _name = 'sale.contract'
    _description = 'Sale Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, default='New')
    name_contract = fields.Char(string='Contract Name', required=True)
    num_contract = fields.Char(string='Contract Number', required=True, copy=False)
    bank = fields.Char(string='Bank Account', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
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
    amount_untaxed = fields.Float(string='Untaxed Amount', store=True)
    amount_tax = fields.Float(string='Tax Amount', store=True)
    amount_total = fields.Float(string='Total', store=True)
    order_line = fields.One2many('sale.order.line', 'order_id', string='Order Lines', store=False)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company.id)
    company_address = fields.Char(string='Company Address', compute='_compute_company_address', store=False)

    @api.depends('company_id')
    def _compute_company_address(self):
        for contract in self:
            contract.company_address = contract.company_id and contract.company_id.partner_id.street or ''
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.contract') or 'New'
        return super(SaleContract, self).create(vals)


    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_create_from_sale_order(self):
        if self.sale_order_id:
            self.contract_lines = [(5, 0, 0)]  # Clear existing lines
            self.amount_total = self.sale_order_id.amount_total
            self.amount_untaxed = self.sale_order_id.amount_untaxed
            self.amount_tax = self.sale_order_id.amount_tax
            for line in self.sale_order_id.order_line:
                self.contract_lines.create({
                    'contract_id': self.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_uom_id': line.product_uom.id,
                    'thong_so': line.x_thongso,
                    'quantity': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'price_subtotal': line.price_subtotal,
                })
    @api.depends('partner_contact_id')
    def _compute_partner_contact_phone(self):
        for order in self:
            phone = order.partner_contact_id.phone or order.partner_contact_id.mobile
            order.partner_contact_phone = phone or ''
    show_contact = fields.Boolean(compute="_compute_show_contact")
class SaleContractLine(models.Model):
    _name = 'sale.contract.line'
    _description = 'Sale Contract Line'

    contract_id = fields.Many2one('sale.contract', string='Contract')
    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Char(string='Description')
    quantity = fields.Float(string='Quantity', default=1.0)
    price_unit = fields.Float(string='Unit Price')
    price_subtotal = fields.Float(string='Subtotal', compute='_compute_price_subtotal', store=True)
    thong_so = fields.Text(string='Technical Specifications')
    product_uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit