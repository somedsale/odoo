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
    terms_conditions = fields.One2many('sale.contract.term', 'contract_id', string='Terms and Conditions')  # Thay Text bằng One2many    
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
                    'tax_id': line.tax_id.id,
                })
    @api.depends('partner_contact_id')
    def _compute_partner_contact_phone(self):
        for order in self:
            phone = order.partner_contact_id.phone or order.partner_contact_id.mobile
            order.partner_contact_phone = phone or ''
    show_contact = fields.Boolean(compute="_compute_show_contact")
    def formatted_price(self, price):
        
            # Định dạng giá trị thành chuỗi, ví dụ: 563.000 đ
            return '{:,.0f} ₫'.format(price).replace(',', '.')   
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
    tax_id = fields.Many2one('account.tax', string='Tax', domain=[('type_tax_use', '=', 'sale')])
    @api.depends('quantity', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
class SaleContractTerm(models.Model):
    _name = 'sale.contract.term'
    _description = 'Sale Contract Term'
    _parent_store = True
    _parent_name = 'parent_id'
    _order = 'sequence, id'

    contract_id = fields.Many2one('sale.contract', string='Contract', required=True, ondelete='cascade')
    parent_id = fields.Many2one('sale.contract.term', string='Parent Term', index=True)
    parent_path = fields.Char(index=True)

    child_ids = fields.One2many('sale.contract.term', 'parent_id', string='Sub Terms')

    sequence = fields.Integer(string='Sequence', default=1)
    name = fields.Char(string='Title', required=True)
    description = fields.Text(string='Description')

    full_name = fields.Char(string='Numbering', compute='_compute_full_name', store=True)
    level = fields.Integer(string='Level', compute='_compute_level', store=True)

    @api.depends('parent_id')
    def _compute_level(self):
        for term in self:
            level = 0
            parent = term.parent_id
            while parent:
                level += 1
                parent = parent.parent_id
            term.level = level

    @api.depends('parent_id.full_name', 'sequence')
    def _compute_full_name(self):
        for term in self:
            if term.parent_id and term.parent_id.full_name:
                term.full_name = f"{term.parent_id.full_name}{term.sequence}."
            else:
                term.full_name = f"{term.sequence}."