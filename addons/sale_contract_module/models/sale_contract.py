from odoo import models, fields, api

class SaleContract(models.Model):
    _name = 'sale.contract'
    _description = 'Sale Contract'

    name = fields.Char(string='Contract Reference', required=True, copy=False, readonly=True, default='New')
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', required=True)
    date = fields.Date(string='Date', default=fields.Date.today)
    amount_total = fields.Float(string='Total Amount', compute='_compute_amount_total')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ], string='Status', default='draft')
    contract_details = fields.Text(string='Contract Details')

    @api.depends('sale_order_id')
    def _compute_amount_total(self):
        for record in self:
            record.amount_total = record.sale_order_id.amount_total if record.sale_order_id else 0.0

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