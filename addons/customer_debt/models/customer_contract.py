# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CustomerContract(models.Model):
    _name = 'customer.contract'
    _description = 'Hợp đồng khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    # Thông tin cơ bản
    name = fields.Char(
        string="Mã hợp đồng", 
        required=True, 
        readonly=True, 
        copy=False, 
        default="New"
    )
    contract_number = fields.Char(string="Số hợp đồng", tracking=True)
    date = fields.Date(string="Ngày ký", default=fields.Date.today, tracking=True)
    partner_id = fields.Many2one(
        'res.partner', 
        string="Khách hàng", 
        required=True, 
        tracking=True
    )
    amount_total = fields.Monetary(
        string="Giá trị HĐ", 
        currency_field="currency_id"
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string="Tiền tệ", 
        default=lambda self: self.env.company.currency_id
    )

    # Liên kết với Hóa đơn
    invoice_ids = fields.One2many(
        'customer.invoice', 
        'contract_id', 
        string="Hóa đơn"
    )

    # Các trường tính toán
    amount_invoiced = fields.Monetary(
        string="Đã xuất hóa đơn", 
        currency_field="currency_id",
        compute="_compute_amounts", 
        store=True
    )
    amount_due = fields.Monetary(
        string="Còn nợ (theo hóa đơn)", 
        currency_field="currency_id",
        compute="_compute_amounts", 
        store=True
    )

    warranty_amount = fields.Monetary(
        string="Giá trị bảo hành", 
        currency_field="currency_id"
    )
    warranty_time = fields.Integer(string="Thời gian bảo hành (tháng)")
    @api.model
    def create(self, vals):
        if vals.get('name', "New") == "New":
            vals['name'] = self.env['ir.sequence'].next_by_code('customer.contract') or "New"
        return super().create(vals)

    @api.depends('invoice_ids.amount_total')
    def _compute_amounts(self):
        """
        Tính tổng giá trị hóa đơn & công nợ còn lại của hợp đồng.
        """
        for contract in self:
            invoiced = sum(contract.invoice_ids.mapped('amount_total'))
            contract.amount_invoiced = invoiced
            contract.amount_due = invoiced
    def name_get(self):
        result = []
        for rec in self:
            if rec.contract_number:
                display = f"[{rec.contract_number}] {rec.name}"
            else:
                display = rec.name
            result.append((rec.id, display))
        return result
