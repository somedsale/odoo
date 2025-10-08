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
        tracking=True,
        domain="[('customer_rank', '>', 0), ('parent_id', '=', False)]"
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
    settlement_ids = fields.One2many(
    'customer.settlement',
    'contract_id',
    string="Hồ sơ quyết toán"
)
    receipt_ids = fields.One2many(
    'account.receipt',
    'contract_id',
    string='Phiếu thu'
)

    # Các trường tính toán
    amount_invoiced = fields.Monetary(
        string="Đã xuất hóa đơn", 
        currency_field="currency_id",
        compute="_compute_amounts", 
        store=True
    )
    amount_receipt = fields.Monetary(
        string="Số tiền đã thu", 
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
    project_id = fields.Many2one(
    'project.project',
    string="Dự án",
    ondelete="set null",
    require=True
)
    @api.model
    def create(self, vals):
        if vals.get('name', "New") == "New":
            vals['name'] = self.env['ir.sequence'].next_by_code('customer.contract') or "New"
        return super().create(vals)

    @api.depends('invoice_ids.amount_total', 'receipt_ids.amount')
    def _compute_amounts(self):
        """
        Tính toán:
        - Đã xuất hóa đơn = tổng giá trị hóa đơn
        - Đã thu = tổng giá trị phiếu thu
        - Còn nợ = Hóa đơn - Thu
        """
        for contract in self:
            invoiced = sum(contract.invoice_ids.mapped('amount_total'))
            received = sum(contract.receipt_ids.mapped('amount'))
            contract.amount_invoiced = invoiced
            contract.amount_receipt = received
            contract.amount_due = invoiced - received
    display_name = fields.Char(
        string="Hiển thị",
        compute="_compute_display_name",
        store=True
    )
    @api.depends('contract_number', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.contract_number:
                rec.display_name = f"[{rec.contract_number}] {rec.name}"
            else:
                rec.display_name = rec.name
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id and self.project_id.partner_id:
            self.partner_id = self.project_id.partner_id
