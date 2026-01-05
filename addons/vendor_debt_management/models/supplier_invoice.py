# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SupplierInvoice(models.Model):
    _name = "supplier.invoice"
    _description = "Supplier Invoice"
    # _rec_name = "invoice_number"
    # Mã hóa đơn (sequence)
    name = fields.Char(
        string="Mã hóa đơn",
        required=True,
        readonly=True,
        copy=False,
        default="New",
    )
    display_name = fields.Char(
        string="Tên hiển thị",
        compute="_compute_display_name",
        store=True,
        readonly=True,
    )
    # Số hóa đơn thực tế
    invoice_number = fields.Char(
        string="Số hóa đơn",
        help="Số hóa đơn thật trên chứng từ nhà cung cấp."
    )

    contract_id = fields.Many2one("supplier.contract", string="Hợp đồng")
    settlement_id = fields.Many2one("supplier.settlement", string="Hồ sơ quyết toán")
    date = fields.Date("Ngày hóa đơn", required=True)

    amount = fields.Monetary("Tổng tiền (sau thuế)", required=True, currency_field="currency_id")
    amount_untaxed = fields.Monetary(
        "Giá trị trước thuế",
        currency_field="currency_id",
        compute="_compute_amounts",
        inverse="_inverse_amounts",
        store=True,
    )
    amount_tax = fields.Monetary(
        "Tiền thuế",
        currency_field="currency_id",
        compute="_compute_amounts",
        inverse="_inverse_amounts",
        store=True,
    )

    account_tax_id = fields.Many2one(
        "account.tax",
        string="Thuế suất áp dụng",
        domain=[('type_tax_use', '=', 'purchase')],
        help="Thuế suất được áp dụng cho hóa đơn này.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        default=lambda self: self.env.company.currency_id,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        compute="_compute_partner_id",
        store=True,
        readonly=False,
    )

    purchase_id = fields.Many2one("purchase.order", string="Đơn mua hàng", index=True)
    project_id = fields.Many2one("project.project", string="Dự án", store=True)
    due_date = fields.Date("Ngày đến hạn")
    note = fields.Text("Diễn giải")
    account_payment_request_ids = fields.One2many(
        "account.payment.request", "invoice_id", string="Phiếu chi"
    )
    cost_classification = fields.Selection([
        ('employee', 'Khoản vay nội bộ(nhân viên)'),
        ('office', 'Chi phí tại công ty'),
        ('project', 'Chi phí các công trình'),
        ('fixed_cost', 'Chi phí cố định'),
        ('irregular_expenses', 'Chi phí không thường xuyên'),
        ('loan_interest', 'Chi phí trả lãi vay'),
    ], string="Phân loại chi phí", default='project',required=True)
    # NEW: Khoản mục
    expense_category_id = fields.Many2one(
        'expense.category', string="Khoản mục",
        domain="[('classification', '=', cost_classification)]",
        help="Chọn khoản mục chi tiết phù hợp với Phân loại chi phí."
    )
    is_warehouse = fields.Selection([
        ('warehouse', 'Nhập kho'),
        ('contruction', 'Công trình'),
    ], string="Nhập kho / Công trình")
    # Loại NCC: trong nước / nước ngoài
    supplier_category = fields.Selection(
        [
            ("domestic", "NCC trong nước"),
            ("foreign", "NCC nước ngoài"),
        ],
        string="Loại NCC",
        default="domestic",
        help="Phân loại nhà cung cấp: trong nước hoặc nước ngoài.",
    )

    # Nhóm NCC trong nước: nhân công / vật tư, dịch vụ
    supplier_domestic_type = fields.Selection(
        [
            ("labor", "NCC Nhân công"),
            ("material_service", "NCC Vật tư, dịch vụ"),
        ],
        string="Nhóm NCC trong nước",
        help="Áp dụng khi Loại NCC là 'NCC trong nước'.",
    )

    # Hạng mục cung cấp
    supply_category = fields.Many2one(
        "supplier.supply.category",
        string="Hạng mục cung cấp",
        help="Hạng mục cung cấp của nhà cung cấp.",
    )

    # Đã đối chiếu công nợ
    reconciled = fields.Boolean(
        string="Đã đối chiếu công nợ",
        help="Đánh dấu phiếu chi này đã được đối chiếu công nợ.",
    )

    # ==============================
    # COMPUTE & ONCHANGE
    # ==============================
    def _compute_display_name(self):
        for rec in self:
            if rec.invoice_number:
                rec.display_name = f"{rec.invoice_number} - {rec.name}"
            else:
                rec.display_name = rec.name
    # @api.model
    # def create(self, vals):
    #     """Tự động sinh mã hóa đơn nếu chưa có"""
    #     if vals.get("name", "New") == "New":
    #         vals["name"] = self.env["ir.sequence"].next_by_code("supplier.invoice") or "New"
    #     return super().create(vals)

    @api.depends("contract_id.partner_id", "purchase_id.partner_id")
    def _compute_partner_id(self):
        for rec in self:
            if rec.contract_id and rec.contract_id.partner_id:
                rec.partner_id = rec.contract_id.partner_id
            elif rec.purchase_id and rec.purchase_id.partner_id:
                rec.partner_id = rec.purchase_id.partner_id
            else:
                rec.partner_id = False

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        for rec in self:
            if rec.contract_id:
                rec.project_id = rec.contract_id.project_id.id
                rec.partner_id = rec.contract_id.partner_id.id

    @api.onchange("account_tax_id", "amount_untaxed")
    def _onchange_tax_compute(self):
        for rec in self:
            if rec.account_tax_id and rec.amount_untaxed:
                tax = rec.account_tax_id
                if tax.amount_type == "percent":
                    rec.amount_tax = rec.amount_untaxed * tax.amount / 100
                elif tax.amount_type == "fixed":
                    rec.amount_tax = tax.amount
                else:
                    rec.amount_tax = 0.0
                rec.amount = rec.amount_untaxed + rec.amount_tax

    @api.depends("amount", "amount_tax", "amount_untaxed")
    def _compute_amounts(self):
        for rec in self:
            if rec.amount_untaxed and rec.amount_tax:
                rec.amount = rec.amount_untaxed + rec.amount_tax
            elif rec.amount and not (rec.amount_untaxed or rec.amount_tax):
                rec.amount_untaxed = rec.amount
                rec.amount_tax = 0.0
            else:
                rec.amount = rec.amount_untaxed + rec.amount_tax

    def _inverse_amounts(self):
        for rec in self:
            rec.amount = rec.amount_untaxed + rec.amount_tax

    @api.constrains("date", "due_date")
    def _check_due_date(self):
        for record in self:
            if record.date and record.due_date and record.due_date < record.date:
                raise ValidationError("Ngày đến hạn không được nhỏ hơn Ngày hóa đơn.")

    # _sql_constraints = [
    #     ("unique_invoice_number", "unique(invoice_number)", "Số hóa đơn đã tồn tại, vui lòng nhập số khác."),
    # ]
    _sql_constraints = [
    (
        "unique_invoice_number_partner",
        "unique(partner_id, invoice_number)",
        "Số hóa đơn đã tồn tại cho nhà cung cấp này, vui lòng nhập số khác.",
    ),
]
    @api.model
    def create(self, vals):
        # 1) Sinh mã (sequence) nếu chưa có
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("supplier.invoice") or "New"

        # 2) (khuyến nghị) chuẩn hoá invoice_number để tránh dính '' gây unique “ảo”
        if "invoice_number" in vals:
            inv = (vals.get("invoice_number") or "").strip()
            vals["invoice_number"] = inv or False

        rec = super().create(vals)

        # 3) Tăng supplier_rank
        if rec.partner_id:
            rec.partner_id._increase_rank("supplier_rank")

        return rec
