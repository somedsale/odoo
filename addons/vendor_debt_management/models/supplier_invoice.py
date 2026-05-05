# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class SupplierInvoice(models.Model):
    _name = "supplier.invoice"
    _description = "Supplier Invoice"
    _order = "date desc, create_date desc"

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

    invoice_number = fields.Char(
        string="Số hóa đơn",
        help="Số hóa đơn thật trên chứng từ nhà cung cấp.",
    )

    contract_id = fields.Many2one(
        "supplier.contract",
        string="Hợp đồng",
    )

    settlement_id = fields.Many2one(
        "supplier.settlement",
        string="Hồ sơ quyết toán",
    )

    date = fields.Date(
        string="Ngày hóa đơn",
        required=True,
    )

    amount = fields.Monetary(
        string="Tổng tiền (sau thuế)",
        required=True,
        currency_field="currency_id",
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

    account_tax_id = fields.Many2one(
        "account.tax",
        string="Thuế suất áp dụng",
        domain=[("type_tax_use", "=", "purchase")],
        help="Thuế suất được áp dụng cho hóa đơn này.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self.env.company.currency_id,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        compute="_compute_partner_id",
        store=True,
        readonly=False,
    )

    purchase_id = fields.Many2one(
        "purchase.order",
        string="Đơn mua hàng",
        index=True,
    )

    project_id = fields.Many2one(
        "project.project",
        string="Dự án",
        store=True,
    )

    due_date = fields.Date(
        string="Ngày đến hạn",
    )

    note = fields.Text(
        string="Diễn giải",
    )

    account_payment_request_ids = fields.One2many(
        "account.payment.request",
        "invoice_id",
        string="Phiếu chi",
    )

    no_payment = fields.Boolean(
        string="Không thanh toán",
        default=False,
        help="Tích chọn nếu hóa đơn này chỉ để theo dõi chứng từ, không tạo phiếu chi và không tính công nợ.",
    )

    cost_classification = fields.Selection(
        [
            ("employee", "Khoản vay nội bộ(nhân viên)"),
            ("office", "Chi phí tại công ty"),
            ("project", "Chi phí các công trình"),
            ("fixed_cost", "Chi phí cố định"),
            ("irregular_expenses", "Chi phí không thường xuyên"),
            ("loan_interest", "Chi phí trả lãi vay"),
        ],
        string="Phân loại chi phí",
        default="project",
        required=True,
    )

    expense_category_id = fields.Many2one(
        "expense.category",
        string="Khoản mục",
        domain="[('classification', '=', cost_classification)]",
        help="Chọn khoản mục chi tiết phù hợp với Phân loại chi phí.",
    )

    is_warehouse = fields.Selection(
        [
            ("warehouse", "Nhập kho"),
            ("contruction", "Công trình"),
        ],
        string="Nhập kho / Công trình",
    )

    supplier_category = fields.Selection(
        [
            ("domestic", "NCC trong nước"),
            ("foreign", "NCC nước ngoài"),
        ],
        string="Loại NCC",
        default="domestic",
        help="Phân loại nhà cung cấp: trong nước hoặc nước ngoài.",
    )

    supplier_domestic_type = fields.Selection(
        [
            ("labor", "NCC Nhân công"),
            ("material_service", "NCC Vật tư, dịch vụ"),
        ],
        string="Nhóm NCC trong nước",
        help="Áp dụng khi Loại NCC là 'NCC trong nước'.",
    )

    supply_category = fields.Many2one(
        "supplier.supply.category",
        string="Hạng mục cung cấp",
        help="Hạng mục cung cấp của nhà cung cấp.",
    )

    reconciled = fields.Boolean(
        string="Đã đối chiếu công nợ",
        help="Đánh dấu phiếu chi này đã được đối chiếu công nợ.",
    )

    # QUAN TRỌNG:
    # Giữ nguyên relation cũ để KHÔNG MẤT FILE CŨ.
    # Không được xóa supplier_invoice_ir_attachments_rel / supplier_invoice_id / attachment_id.
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "supplier_invoice_ir_attachments_rel",
        "supplier_invoice_id",
        "attachment_id",
        string="Tệp đính kèm",
        help="Đính kèm hóa đơn, báo giá, biên bản, chứng từ liên quan.",
    )

    _sql_constraints = [
        (
            "unique_invoice_number_partner",
            "unique(partner_id, invoice_number)",
            "Số hóa đơn đã tồn tại cho nhà cung cấp này, vui lòng nhập số khác.",
        ),
    ]

    # =========================
    # MIGRATION / REPAIR ATTACHMENT
    # =========================

    def init(self):
        """
        Tự sửa file cũ khi update module.

        File cũ đang nằm trong bảng Many2many:
            supplier_invoice_ir_attachments_rel

        Hàm này gán lại:
            ir_attachment.res_model = 'supplier.invoice'
            ir_attachment.res_id = supplier_invoice_id

        Nhờ vậy attachment đi theo cơ chế chuẩn của Odoo hơn,
        giảm lỗi Access Error với ir.attachment.
        """
        self.env.cr.execute("""
            UPDATE ir_attachment AS att
               SET res_model = 'supplier.invoice',
                   res_id = rel.supplier_invoice_id
              FROM supplier_invoice_ir_attachments_rel AS rel
             WHERE att.id = rel.attachment_id
               AND rel.supplier_invoice_id IS NOT NULL
               AND rel.attachment_id IS NOT NULL
               AND (
                    att.res_model IS NULL
                    OR att.res_model = ''
                    OR att.res_model != 'supplier.invoice'
                    OR att.res_id IS NULL
                    OR att.res_id = 0
               )
        """)

    def _sync_attachment_res_model_res_id(self):
        """
        Đồng bộ attachment của hóa đơn hiện tại về đúng res_model/res_id.

        Dùng sudo() vì thao tác này là thao tác kỹ thuật để sửa metadata file,
        tránh user bị chặn khi đang lưu form.
        """
        for rec in self.sudo():
            if not rec.id or not rec.attachment_ids:
                continue

            rec.attachment_ids.sudo().write({
                "res_model": rec._name,
                "res_id": rec.id,
            })

    @api.model
    def action_repair_all_supplier_invoice_attachments(self):
        """
        Có thể gọi thủ công trong Odoo shell nếu cần:

        env['supplier.invoice'].action_repair_all_supplier_invoice_attachments()
        """
        self.env.cr.execute("""
            UPDATE ir_attachment AS att
               SET res_model = 'supplier.invoice',
                   res_id = rel.supplier_invoice_id
              FROM supplier_invoice_ir_attachments_rel AS rel
             WHERE att.id = rel.attachment_id
               AND rel.supplier_invoice_id IS NOT NULL
               AND rel.attachment_id IS NOT NULL
        """)
        return True

    # =========================
    # COMPUTE / ONCHANGE
    # =========================

    @api.depends("invoice_number", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.invoice_number:
                rec.display_name = "%s - %s" % (rec.invoice_number, rec.name or "")
            else:
                rec.display_name = rec.name or ""

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
                rec.project_id = rec.contract_id.project_id
                rec.partner_id = rec.contract_id.partner_id

    @api.onchange("account_tax_id", "amount_untaxed")
    def _onchange_tax_compute(self):
        for rec in self:
            amount_untaxed = rec.amount_untaxed or 0.0
            amount_tax = 0.0

            if rec.account_tax_id and amount_untaxed:
                tax = rec.account_tax_id

                if tax.amount_type == "percent":
                    amount_tax = amount_untaxed * tax.amount / 100.0
                elif tax.amount_type == "fixed":
                    amount_tax = tax.amount
                else:
                    amount_tax = 0.0

            rec.amount_tax = amount_tax
            rec.amount = amount_untaxed + amount_tax

    @api.depends("amount", "amount_tax", "amount_untaxed")
    def _compute_amounts(self):
        for rec in self:
            amount = rec.amount or 0.0
            amount_untaxed = rec.amount_untaxed or 0.0
            amount_tax = rec.amount_tax or 0.0

            if amount_untaxed or amount_tax:
                rec.amount = amount_untaxed + amount_tax
            elif amount:
                rec.amount_untaxed = amount
                rec.amount_tax = 0.0
            else:
                rec.amount_untaxed = 0.0
                rec.amount_tax = 0.0

    def _inverse_amounts(self):
        for rec in self:
            rec.amount = (rec.amount_untaxed or 0.0) + (rec.amount_tax or 0.0)

    # =========================
    # CONSTRAINTS
    # =========================

    @api.constrains("date", "due_date")
    def _check_due_date(self):
        for rec in self:
            if rec.date and rec.due_date and rec.due_date < rec.date:
                raise ValidationError("Ngày đến hạn không được nhỏ hơn Ngày hóa đơn.")

    @api.constrains("no_payment", "account_payment_request_ids")
    def _check_no_payment_with_payment_requests(self):
        for rec in self:
            if rec.no_payment and rec.account_payment_request_ids:
                raise ValidationError(
                    "Hóa đơn đã tích 'Không thanh toán' thì không được có phiếu chi."
                )

    # =========================
    # CRUD
    # =========================

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = self.env["ir.sequence"].next_by_code("supplier.invoice") or "New"

        if "invoice_number" in vals:
            inv = (vals.get("invoice_number") or "").strip()
            vals["invoice_number"] = inv or False

        rec = super().create(vals)

        if rec.partner_id:
            rec.partner_id._increase_rank("supplier_rank")

        rec._sync_attachment_res_model_res_id()

        return rec

    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            if rec.no_payment and rec.account_payment_request_ids:
                raise ValidationError(
                    "Hóa đơn đã tích 'Không thanh toán' thì không được có phiếu chi."
                )

        if "attachment_ids" in vals:
            self._sync_attachment_res_model_res_id()

        return res