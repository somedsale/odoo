# -*- coding: utf-8 -*-
from odoo import models, fields,api

class CustomerInvoice(models.Model):
    _name = 'customer.invoice'
    _description = 'Hóa đơn khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string="Mã hóa đơn", 
        required=True, 
        readonly=True, 
        copy=False, 
        default="New"
    )

    # Số hóa đơn thật (người dùng nhập tay)
    invoice_number = fields.Char(string="Số hóa đơn", tracking=True)
    date = fields.Date(string="Ngày Hóa Đơn", default=fields.Date.today)
    partner_id = fields.Many2one('res.partner', string="Khách hàng", required=True,domain="[('customer_rank', '>', 0), ('parent_id', '=', False)]")
    
    # Gắn hợp đồng (nếu có) – không bắt buộc
    contract_id = fields.Many2one(
        'customer.contract', 
        string="Hợp đồng", 
        ondelete="set null"
    )

    amount_total = fields.Monetary(string="Giá trị hóa đơn", currency_field="currency_id")
    currency_id = fields.Many2one(
        'res.currency', 
        string="Tiền tệ", 
        default=lambda self: self.env.company.currency_id
    )
    project_id = fields.Many2one(
    'project.project',
    string="Dự án",
    ondelete="set null"
)
    display_name = fields.Char(
        string="Hiển thị",
        compute="_compute_display_name",
        store=True
    )
    @api.depends('name', 'invoice_number')
    def _compute_display_name(self):
        for rec in self:
            if rec.invoice_number:
                rec.display_name = f"[{rec.invoice_number}] {rec.name}"
            else:
                rec.display_name = rec.name
    @api.model
    def create(self, vals):
        if vals.get('name', "New") == "New":
            vals['name'] = self.env['ir.sequence'].next_by_code('customer.invoice') or "New"
        return super().create(vals)
    @api.model
    def default_get(self, fields_list):
        """Khi tạo hóa đơn từ hợp đồng -> gán luôn partner và project"""
        res = super().default_get(fields_list)
        if self.env.context.get('default_contract_id'):
            contract = self.env['customer.contract'].browse(self.env.context['default_contract_id'])
            if contract:
                if contract.partner_id:
                    res['partner_id'] = contract.partner_id.id
                if contract.project_id:
                    res['project_id'] = contract.project_id.id
        return res
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.project_id = self.contract_id.project_id
    