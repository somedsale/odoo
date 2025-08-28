from odoo import models, fields, api

class SupplierDebt(models.Model):
    _name = 'supplier.debt'
    _description = 'Supplier Debt Record'
    
    name = fields.Char(string="Reference", required=True, copy=False, readonly=True, default=lambda self: 'New')
    supplier_id = fields.Many2one('res.partner', string="Nhà cung cấp", domain="[('supplier_rank', '>', 0)]", required=True)
    project_id = fields.Many2one('project.project', string="Dự án")
    contract_id = fields.Many2one('purchase.contract', string="Purchase Contract")
    total_amount = fields.Float(string="Total Amount", required=True)
    paid_amount = fields.Float(string="Paid Amount", default=0.0)
    remaining_amount = fields.Float(string="Remaining Amount", compute='_compute_remaining_amount', store=True)
    currency_id = fields.Many2one('res.currency', string="Currency", required=True, default=lambda self: self.env.company.currency_id)

    @api.depends('total_amount', 'paid_amount')
    def _compute_remaining_amount(self):
        for record in self:
            record.remaining_amount = record.total_amount - record.paid_amount

    def action_confirm(self):
        for record in self:
            record.state = 'confirmed'

    def action_settle(self):
        for record in self:
            if record.remaining_amount <= 0:
                record.state = 'settled'
            else:
                raise ValueError("Cannot settle debt with remaining amount greater than zero.")
class SupplierDebtSummary(models.Model):
    _name = 'supplier.debt.summary'
    _description = 'Supplier Debt Summary'
    name = fields.Char(string="Summary Reference", required=True, copy=False, readonly=True, default=lambda self: 'New')
    supplier_id = fields.Many2one('res.partner', string="Nhà cung cấp",
        domain="[('supplier_rank', '>', 0)]", required=True)
    total_debt = fields.Float(string="Total Debt", compute='_compute_total_debt', store=True)
    total_paid = fields.Float(string="Total Paid", compute='_compute_total_debt', store=True)
    total_remaining = fields.Float(string="Total Remaining", compute='_compute_total_debt', store=True)
    currency_id = fields.Many2one('res.currency', string="Currency", required=True, default=lambda self: self.env.company.currency_id)
    debt_line_ids = fields.One2many('supplier.debt', 'supplier_id', string="Debt Lines", domain="[('supplier_id', '=', supplier_id)]")

    @api.depends('debt_line_ids.total_amount', 'debt_line_ids.paid_amount')
    def _compute_total_debt(self):
        for record in self:
            debts = record.debt_line_ids
            record.total_debt = sum(debt.total_amount for debt in debts)
            record.total_paid = sum(debt.paid_amount for debt in debts)
            record.total_remaining = sum(debt.remaining_amount for debt in debts)