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
    contact = fields.Text(string="Liên hệ")
    amount_total = fields.Monetary(
        string="Giá trị HĐ",
        currency_field="currency_id",
        compute="_compute_amount_total",
        store=True,
        tracking=True
    )
    currency_id = fields.Many2one(
        'res.currency', 
        string="Tiền tệ", 
        default=lambda self: self.env.company.currency_id
    )
    management_id = fields.Many2one(
        'contract.management',
        string="Hồ sơ quản lý HĐ (Sale)",
        ondelete="set null",
        tracking=True
    )
    amount_untaxed = fields.Monetary(
        string="Giá trị chưa thuế", 
        currency_field="currency_id",
        store=True
    )
    tax_id = fields.Many2many(
        'account.tax', 
        string="Thuế", 
        help="Các sắc thuế áp dụng cho hợp đồng."
    )
    attachment_ids = fields.Many2many(
        'ir.attachment', 
        string="Tài liệu",
        related='management_id.attachment_ids'
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
    contract_type = fields.Selection([
    ('preparing', 'Công trình đang chuẩn bị thực hiện'),
    ('done', 'Đã hoàn thành'),
    ('paused', 'Tạm ngưng'),
    ('bad_debt', 'Công nợ khó đòi'),
], string="Loại hợp đồng", default='preparing', tracking=True)
    @api.depends('amount_untaxed', 'tax_id')
    def _compute_amount_total(self):
        """
        Giá trị hợp đồng = Giá trị chưa thuế + tổng thuế
        Nếu hợp đồng cũ chưa có amount_untaxed → mặc định bằng amount_total hiện có
        """
        for contract in self:
            if not contract.amount_untaxed and contract.amount_total:
                # giữ nguyên giá trị cũ
                contract.amount_untaxed = contract.amount_total

            taxes_amount = 0.0
            if contract.tax_id:
                # Tính tổng % thuế
                taxes_percent = sum(contract.tax_id.mapped('amount'))
                taxes_amount = contract.amount_untaxed * taxes_percent / 100

            contract.amount_total = contract.amount_untaxed + taxes_amount
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
    @api.onchange('project_id', 'partner_id')
    def _onchange_project_or_partner(self):
        for rec in self:
            management = False

            if rec.project_id:
                rec.partner_id = rec.project_id.partner_id or False
            else:
                rec.partner_id = False

            # Ưu tiên tìm hợp đồng bên Sale theo dự án
            if rec.project_id:
                management = rec.env['contract.management'].search([
                    '|',
                    ('project_id', '=', rec.project_id.id),
                    ('sale_order_id.project_id', '=', rec.project_id.id),
                ], limit=1)

            # Nếu chưa thấy → tìm theo khách hàng
            if not management and rec.partner_id:
                management = rec.env['contract.management'].search([
                    ('partner_id', '=', rec.partner_id.id)
                ], limit=1)

            # Gán dữ liệu nếu tìm thấy
            if management:
                rec.management_id = management
                rec.contract_number = management.num_contract
                rec.amount_untaxed = management.contract_value or 0.0
                rec.amount_total = rec.amount_untaxed
                rec.partner_id = management.partner_id.id
            else:
                rec.management_id = False
                rec.contract_number = False
                rec.amount_untaxed = 0.0
                rec.amount_total = 0.0