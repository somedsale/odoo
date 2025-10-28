# -*- coding: utf-8 -*-
from odoo import models, fields, api


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

    invoice_number = fields.Char(string="Số hóa đơn", tracking=True)
    date = fields.Date(string="Ngày Hóa Đơn", default=fields.Date.today)
    partner_id = fields.Many2one(
        'res.partner',
        string="Khách hàng",
        required=True,
        domain="[('customer_rank', '>', 0), ('parent_id', '=', False)]",
    )

    account_receipt_ids = fields.One2many('account.receipt', 'invoice_id', string="Phiếu thu")

    contract_id = fields.Many2one(
        'customer.contract',
        string="Hợp đồng",
        ondelete="set null"
    )

    # ---------- SỐ TIỀN ----------
    amount_total = fields.Monetary(
        string="Tổng sau thuế",
        currency_field="currency_id",
        tracking=True,
    )
    amount_untaxed = fields.Monetary(
        string="Giá trị trước thuế",
        currency_field="currency_id",
        compute="_compute_amounts",
        inverse="_inverse_amounts",
        store=True,
    )
    amount_tax = fields.Monetary(
        string="Tiền thuế",
        currency_field="currency_id",
        compute="_compute_amounts",
        inverse="_inverse_amounts",
        store=True,
    )

    # Thuế suất (bán hàng)
    account_tax_id = fields.Many2one(
        "account.tax",
        string="Thuế suất áp dụng",
        domain=[("type_tax_use", "=", "sale")],
        help="Chỉ chọn các loại thuế dùng cho bán hàng (sale).",
    )

    currency_id = fields.Many2one(
        'res.currency',
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
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

    # -----------------------------
    # HIỂN THỊ
    # -----------------------------
    @api.depends('name', 'invoice_number')
    def _compute_display_name(self):
        for rec in self:
            if rec.invoice_number:
                rec.display_name = f"[{rec.invoice_number}] {rec.name}"
            else:
                rec.display_name = rec.name

    # -----------------------------
    # SEQUENCE
    # -----------------------------
    @api.model
    def create(self, vals):
        if vals.get('name', "New") == "New":
            vals['name'] = self.env['ir.sequence'].next_by_code('customer.invoice') or "New"
        return super().create(vals)

    # -----------------------------
    # DEFAULT GET (tạo từ hợp đồng)
    # -----------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('default_contract_id'):
            contract = self.env['customer.contract'].browse(self.env.context['default_contract_id'])
            if contract:
                if contract.partner_id:
                    res['partner_id'] = contract.partner_id.id
                if contract.project_id:
                    res['project_id'] = contract.project_id.id
        return res

    # -----------------------------
    # ONCHANGE
    # -----------------------------
    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.partner_id = self.contract_id.partner_id
            self.project_id = self.contract_id.project_id

    @api.onchange("account_tax_id", "amount_untaxed")
    def _onchange_tax_compute(self):
        """Tự động tính tiền thuế và tổng khi chọn thuế"""
        for rec in self:
            if rec.account_tax_id and rec.amount_untaxed:
                tax = rec.account_tax_id
                if tax.amount_type == "percent":
                    rec.amount_tax = rec.amount_untaxed * tax.amount / 100
                elif tax.amount_type == "fixed":
                    rec.amount_tax = tax.amount
                else:
                    rec.amount_tax = 0.0
                rec.amount_total = rec.amount_untaxed + rec.amount_tax
            else:
                rec.amount_tax = 0.0
                rec.amount_total = rec.amount_untaxed

    # -----------------------------
    # COMPUTE / INVERSE
    # -----------------------------
    @api.depends("amount_total", "amount_tax", "amount_untaxed")
    def _compute_amounts(self):
        for rec in self:
            if rec.amount_untaxed and rec.amount_tax:
                rec.amount_total = rec.amount_untaxed + rec.amount_tax
            elif rec.amount_total and not (rec.amount_untaxed or rec.amount_tax):
                rec.amount_untaxed = rec.amount_total
                rec.amount_tax = 0.0
            else:
                rec.amount_total = rec.amount_untaxed + rec.amount_tax

    def _inverse_amounts(self):
        for rec in self:
            rec.amount_total = rec.amount_untaxed + rec.amount_tax
