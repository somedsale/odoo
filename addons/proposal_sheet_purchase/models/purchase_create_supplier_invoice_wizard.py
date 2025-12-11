# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class PurchaseCreateSupplierInvoiceWizard(models.TransientModel):
    _name = "purchase.create.supplier.invoice.wizard"
    _description = "Tạo hóa đơn NCC từ Đơn mua"

    # ---- Ngữ cảnh / neo dữ liệu ----
    purchase_id = fields.Many2one(
        "purchase.order",
        string="Đơn mua hàng",
        required=True,
        default=lambda self: self._default_purchase_id(),
        readonly=True,
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        related="purchase_id.partner_id",
        store=False,
        readonly=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        default=lambda self: self._default_currency_id(),
        readonly=True,
    )

    # ---- Thông tin hóa đơn ----
    name = fields.Char("Số hóa đơn", required=True)
    contract_id = fields.Many2one(
        "supplier.contract",
        string="Hợp đồng",
        required=True,
        default=lambda self: self._default_contract_id(),
        domain="[('partner_id', '=', partner_id), ('project_id', '=', purchase_id.proposal_sheet_id.project_id)]",
        help="Chọn hợp đồng tương ứng của NCC/Dự án.",
    )
    settlement_id = fields.Many2one(
        "supplier.settlement",
        string="Hồ sơ quyết toán",
        domain="[('contract_id', '=', contract_id)]",
        help="(Tuỳ chọn) Gắn hóa đơn vào một hồ sơ quyết toán cụ thể của hợp đồng.",
    )
    date = fields.Date("Ngày hóa đơn", required=True, default=fields.Date.context_today)
    due_date = fields.Date("Ngày đến hạn")
    po_amount_untaxed = fields.Monetary(
        string="Giá trị trước thuế (PO)",
        currency_field="currency_id",
        compute="_compute_po_amounts",
    )
    po_amount_tax = fields.Monetary(
        string="Tiền thuế (PO)",
        currency_field="currency_id",
        compute="_compute_po_amounts",
    )
    tax_id = fields.Many2one(
        "account.tax",
        string="Thuế VAT",
        domain=[("type_tax_use", "=", "purchase")],
        default=lambda self: self._default_tax_id(),
        help="Mặc định lấy từ thuế trên Đơn mua. Nếu PO có nhiều loại thuế thì để trống để tự chọn.",
    )

    @api.depends("purchase_id")
    def _compute_po_amounts(self):
        for wiz in self:
            po = wiz.purchase_id
            wiz.po_amount_untaxed = po.amount_untaxed or 0.0
            wiz.po_amount_tax = po.amount_tax or 0.0
    amount = fields.Monetary("Số tiền (Đã bao gồm thuế)", required=True, currency_field="currency_id",
                             default=lambda self: self._default_invoice_amount())
    note = fields.Text("Diễn giải", default="")

    # ---- Liên kết phiếu chi ----
    auto_link_payments = fields.Boolean(
        string="Tự động liên kết phiếu chi có sẵn",
        default=True,
        help="Nếu bật, hệ thống sẽ tự động gán các phiếu chi (post/done) chưa gắn hóa đơn thuộc PO này vào hóa đơn vừa tạo cho tới khi đủ số tiền.",
    )
    payment_request_ids = fields.Many2many(
        "account.payment.request",
        "wiz_supplier_invoice_payreq_rel",
        "wiz_id",
        "payreq_id",
        string="Chọn phiếu chi để liên kết",
        domain=lambda self: self._domain_payment_requests(),
        help="Nếu tắt tự động, bạn có thể chọn thủ công các phiếu chi sẽ gắn vào hóa đơn.",
    )
    suggest_payment_total = fields.Monetary(
        string="Tổng phiếu chi được gợi ý",
        currency_field="currency_id",
        compute="_compute_suggest_payment_total",
        store=False,
    )

    # ------------------------------------------------------------------
    # Defaults
    # ------------------------------------------------------------------
    @api.model
    def _default_tax_id(self):
        """
        Lấy thuế từ các dòng PO:
        - Nếu tất cả dòng dùng 1 loại thuế duy nhất -> trả về thuế đó
        - Nếu nhiều loại thuế khác nhau -> trả False (user tự chọn)
        Hỗ trợ cả chuẩn Odoo (taxes_id) lẫn custom (tax_id).
        """
        active_id = self.env.context.get("active_id")
        if not active_id:
            return False

        po = self.env["purchase.order"].browse(active_id)
        if not po or not po.exists():
            return False

        # Thử lấy theo chuẩn Odoo trước (taxes_id)
        taxes = po.order_line.mapped("taxes_id")
        # Nếu không có thì thử lấy custom field tax_id (nếu anh dùng)
        if not taxes:
            taxes = po.order_line.mapped("tax_id")

        # Chỉ giữ thuế mua hàng
        taxes = taxes.filtered(lambda t: t.type_tax_use == "purchase")
        taxes = taxes.sorted(lambda t: t.id)

        if len(taxes) == 1:
            return taxes.id
        return False
    @api.model
    def _default_purchase_id(self):
        active_id = self.env.context.get("active_id")
        if not active_id:
            raise UserError(_("Wizard cần được mở từ một Đơn mua hàng."))
        po = self.env["purchase.order"].browse(active_id)
        if not po or not po.exists():
            raise UserError(_("Đơn mua hàng không tồn tại."))
        if len(po) != 1:
            raise UserError(_("Vui lòng chọn một Đơn mua hàng duy nhất."))
        return po.id

    @api.model
    def _default_currency_id(self):
        active_id = self.env.context.get("active_id")
        if not active_id:
            return self.env.company.currency_id.id
        po = self.env["purchase.order"].browse(active_id)
        return (po.currency_id.id or self.env.company.currency_id.id)

    @api.model
    def _default_contract_id(self):
        """Ưu tiên PO.supplier_contract_id; nếu chưa có,
        tìm hợp đồng theo NCC + Dự án (nếu có)."""
        active_id = self.env.context.get("active_id")
        if not active_id:
            return False
        po = self.env["purchase.order"].browse(active_id)
        if po and po.exists() and getattr(po, "supplier_contract_id", False):
            return po.supplier_contract_id.id

        partner = po.partner_id
        project = getattr(po.proposal_sheet_id, "project_id", False)
        if partner and project:
            contract = self.env["supplier.contract"].search([
                ("partner_id", "=", partner.id),
                ("project_id", "=", project.id),
            ], limit=1)
            return contract.id
        return False

    @api.model
    def _default_invoice_amount(self):
        """Mặc định: số tiền hóa đơn = tổng PO (có thể sửa tay)."""
        active_id = self.env.context.get("active_id")
        if not active_id:
            return 0.0
        po = self.env["purchase.order"].browse(active_id)
        return float(po.amount_total or 0.0)

    # ------------------------------------------------------------------
    # Helpers / Onchanges
    # ------------------------------------------------------------------
    @api.model
    def _domain_payment_requests(self):
        """Chỉ các phiếu chi từ PO hiện tại, chưa gắn hóa đơn.
        Ưu tiên trạng thái đã vào sổ/hoàn tất (post/done)."""
        active_id = self.env.context.get("active_id")
        return [
            ("purchase_id", "=", active_id or 0),
            ("invoice_id", "=", False),
            ("state", "in", ["post", "done", "confirmed"]),
        ]

    @api.depends("payment_request_ids.total")
    def _compute_suggest_payment_total(self):
        for wiz in self:
            wiz.suggest_payment_total = sum(wiz.payment_request_ids.mapped("total"))

    @api.onchange("auto_link_payments")
    def _onchange_auto_link_payments(self):
        if self.auto_link_payments:
            # Xóa chọn thủ công khi bật auto (tránh hiểu nhầm)
            self.payment_request_ids = [(5, 0, 0)]

    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        # Khi đổi hợp đồng, xóa settlement đang chọn để tránh sai liên kết
        self.settlement_id = False

    @api.constrains("date", "due_date")
    def _check_due_date(self):
        for w in self:
            if w.date and w.due_date and w.due_date < w.date:
                raise ValidationError(_("Ngày đến hạn không được nhỏ hơn Ngày hóa đơn."))

    @api.constrains("amount")
    def _check_amount(self):
        for w in self:
            if (w.amount or 0.0) <= 0.0:
                raise ValidationError(_("Số tiền hóa đơn phải lớn hơn 0."))

    # ------------------------------------------------------------------
    # Core: Create invoice + link payments
    # ------------------------------------------------------------------
    def _collect_auto_payments(self, po, amount_needed):
        """Trả về các payment requests (post/done/confirmed, chưa có invoice) của PO,
        ưu tiên theo ngày thanh toán rồi id, gán cho tới khi đủ amount_needed."""
        PayReq = self.env["account.payment.request"]
        domain = [
            ("purchase_id", "=", po.id),
            ("invoice_id", "=", False),
            ("state", "in", ["post", "done", "confirmed"]),
        ]
        candidates = PayReq.search(domain).sorted(
            key=lambda r: (r.date_payment or r.create_date or fields.Datetime.now(), r.id)
        )
        chosen = self.env["account.payment.request"]
        running = 0.0
        for pr in candidates:
            if running >= amount_needed:
                break
            chosen |= pr
            running += float(pr.total or 0.0)
        return chosen

    def _create_invoice_record(self):
        """Tạo 1 bản ghi supplier.invoice dựa trên wizard."""
        self.ensure_one()
        po = self.purchase_id
        if po.state not in ("purchase", "done"):
            raise UserError(_("Chỉ tạo hóa đơn cho Đơn mua đã xác nhận."))

        if not self.contract_id:
            raise UserError(_("Vui lòng chọn Hợp đồng để liên kết hóa đơn."))

        vals = {
            "name": self.name.strip(),
            "contract_id": self.contract_id.id,
            "settlement_id": self.settlement_id.id if self.settlement_id else False,
            "purchase_id": po.id,
            "date": self.date,
            "due_date": self.due_date,
            "amount": self.amount,
            "currency_id": self.currency_id.id,
            "note": self.note or "",
        }
        invoice = self.env["supplier.invoice"].create(vals)
        return invoice

    def _link_payments_to_invoice(self, invoice):
        """Gán invoice_id cho các payment request được chọn/tự động gợi ý."""
        self.ensure_one()
        po = self.purchase_id
        amount_needed = float(self.amount or 0.0)

        # Nếu bật auto-link -> tự lấy các phiếu (post/done/confirmed) chưa gắn hóa đơn
        chosen = self.env["account.payment.request"]
        if self.auto_link_payments:
            chosen = self._collect_auto_payments(po, amount_needed)
        else:
            chosen = self.payment_request_ids

        if chosen:
            chosen.write({"invoice_id": invoice.id})

    # ------------------------------------------------------------------
    # Public action
    # ------------------------------------------------------------------
    def action_confirm(self):
        self.ensure_one()
        po = self.purchase_id
        amount_untaxed = po.amount_untaxed
        amount_tax = po.amount_tax
        amount_total = po.amount_total

        # tạo hóa đơn
        invoice = self.env["supplier.invoice"].create({
            "name": self.name,
            "purchase_id": po.id,
            "contract_id": self.contract_id.id,
            "date": self.date,
            "due_date": self.due_date,
            "amount": self.amount,
            "amount_untaxed": amount_untaxed,
            "amount_tax": amount_tax,
            "account_tax_id": self.tax_id.id if self.tax_id else False,
            "currency_id": self.currency_id.id or self.env.company.currency_id.id,
            "note": self.note or "",
        })

        # mở form hóa đơn mới tạo
        return {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn NCC",
            "res_model": "supplier.invoice",
            "view_mode": "form",
            "res_id": invoice.id,
            "target": "current",
            "context": {
                "default_purchase_id": po.id,
                "default_contract_id": self.contract_id.id,
            },
        }
