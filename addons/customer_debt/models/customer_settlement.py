# -*- coding: utf-8 -*-
from odoo import models, fields, api

class CustomerSettlement(models.Model):
    _name = 'customer.settlement'
    _description = 'Hồ sơ quyết toán khách hàng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    # ====== Cơ bản ======
    name = fields.Char(
        string="Mã hồ sơ",
        required=True,
        readonly=True,
        copy=False,
        default="New"
    )
    settlement_number = fields.Char(
        string="Số hồ sơ",
        tracking=True
    )
    date = fields.Date(
        string="Ngày quyết toán",
        default=fields.Date.today,
        tracking=True
    )

    # ====== Liên kết ======
    contract_id = fields.Many2one(
        'customer.contract',
        string="Hợp đồng",
        ondelete='cascade',
        tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string="Khách hàng",
        readonly=True
    )
    project_id = fields.Many2one(
        'project.project',
        string="Dự án",
        readonly=True
    )

    # ====== Số tiền ======
    amount_settlement = fields.Monetary(
        string="Số tiền quyết toán",
        currency_field="currency_id",
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency',
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id
    )

    # ====== Hiển thị ======
    display_name = fields.Char(
        string="Hiển thị",
        compute="_compute_display_name",
        store=True
    )

    @api.depends('settlement_number', 'name')
    def _compute_display_name(self):
        for rec in self:
            if rec.settlement_number:
                rec.display_name = f"[{rec.settlement_number}] {rec.name}"
            else:
                rec.display_name = rec.name

    # ====== Auto sequence ======
    @api.model
    def create(self, vals):
        if vals.get('name', "New") == "New":
            vals['name'] = self.env['ir.sequence'].next_by_code('customer.settlement') or "New"
        # Gắn thông tin partner & project từ hợp đồng
        if vals.get('contract_id'):
            contract = self.env['customer.contract'].browse(vals['contract_id'])
            if contract:
                vals['partner_id'] = contract.partner_id.id
                vals['project_id'] = contract.project_id.id
        return super().create(vals)

    # ====== onchange ======
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.project_id = self.contract_id.project_id
            self.currency_id = self.contract_id.currency_id
