# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from datetime import date
from collections import OrderedDict


class SupplierInvoicePaymentSummary(models.Model):
    _name = "supplier.invoice.payment.summary"
    _description = "Tổng hợp công nợ NCC theo hóa đơn & phiếu chi"
    _auto = False
    _rec_name = "partner_id"

    # ========== THÔNG TIN CHÍNH ==========
    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        domain=[("supplier_rank", ">", 0)],
    )
    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
    )

    # Danh sách hóa đơn & phiếu chi của NCC này (theo currency)
    invoice_ids = fields.One2many(
        "supplier.invoice",
        compute="_compute_invoice_ids",
        inverse="_inverse_invoice_ids",
        string="Hóa đơn",
    )
    payment_request_ids = fields.One2many(
        "account.payment.request",
        compute="_compute_payment_request_ids",
        inverse="_inverse_payment_request_ids",
        string="Phiếu chi",
    )

    # 🔹 Danh sách HỢP ĐỒNG NCC (theo NCC + tiền tệ)
    contract_ids = fields.One2many(
        "supplier.contract",
        compute="_compute_contract_ids",
        inverse="_inverse_contract_ids",
        string="Hợp đồng NCC",
    )

    # Ngày đến hạn gần nhất trong các hóa đơn
    due_date = fields.Date(
        "Ngày đến hạn",
        compute="_compute_due_date",
    )
    due_days = fields.Char(
        "Số ngày đến hạn",
        compute="_compute_due_date",
    )
    due_days_html = fields.Html(
        "Số ngày đến hạn (màu)",
        compute="_compute_due_days_html",
        sanitize=False,
    )

    # Tổng giá trị hợp đồng & quyết toán
    total_contract_amount = fields.Monetary(
        "Tổng giá trị hợp đồng",
        compute="_compute_total_contract_amount",
        currency_field="currency_id",
    )
    total_settlements_amount = fields.Monetary(
        "Tổng giá trị hồ sơ quyết toán",
        compute="_compute_total_settlements_amount",
        currency_field="currency_id",
    )

    # ========== TỔNG HỢP SỐ TIỀN ==========
    total_invoice_amount = fields.Monetary(
        "Tổng giá trị hóa đơn",
        compute="_compute_total_invoice_amount",
        currency_field="currency_id",
    )
    total_payment_amount = fields.Monetary(
        "Tổng giá trị phiếu chi",
        compute="_compute_total_payment_amount",
        currency_field="currency_id",
    )
    residual_amount = fields.Monetary(
        "Còn nợ",
        compute="_compute_residual_and_advance",
        currency_field="currency_id",
    )
    advance_amount = fields.Monetary(
        "Tạm ứng / Chi chưa hóa đơn",
        compute="_compute_residual_and_advance",
        currency_field="currency_id",
    )

    # ========== GHI CHÚ / DIỄN GIẢI / CÔNG NỢ CŨ / ĐỐI CHIẾU ==========
    note = fields.Text(
        "Ghi chú",
        compute="_compute_note",
        inverse="_inverse_note",
        store=False,
    )
    interpretation = fields.Char(
        "Diễn giải",
        compute="_compute_interpretation",
        inverse="_inverse_interpretation",
        store=False,
    )
    old_debt = fields.Monetary(
        string="Công nợ cũ",
        currency_field="currency_id",
        compute="_compute_old_debt",
        inverse="_inverse_old_debt",
        store=False,
        help="Số tiền còn nợ trước đây (ghi trong note + old_debt từng hợp đồng).",
    )
    # 🔹 Checkbox đối chiếu công nợ
    reconciled = fields.Boolean(
        string="Đã đối chiếu công nợ",
        compute="_compute_reconciled",
        inverse="_inverse_reconciled",
        store=False,
        help="Đánh dấu đã đối chiếu công nợ với nhà cung cấp.",
    )
    supplier_category = fields.Selection(
        [
            ("domestic", "Nhà cung cấp trong nước"),
            ("foreign", "Nhà cung cấp nước ngoài"),
        ],
        default="domestic",
        string="Loại nhà cung cấp",
        compute="_compute_supplier_category",
        inverse="_inverse_supplier_category",
        store=False,
    )
    supplier_domestic_type = fields.Selection(
        [
            ("labor", "Nhà cung cấp Nhân công"),
            ("material_service", "Nhà cung cấp Vật tư, dịch vụ"),
        ],
        string="Loại nhà cung cấp trong nước",
        compute="_compute_supplier_domestic_type",
        inverse="_inverse_supplier_domestic_type",
        store=False,
    )   
    supply_category = fields.Many2one(
        "supplier.supply.category",
        string="Hạng mục cung cấp",
        compute="_compute_supply_category",
        inverse="_inverse_supply_category",
        store=False,
    )
    # =====================================================
    # SQL VIEW
    # =====================================================
    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    sub.partner_id,
                    sub.currency_id
                FROM (
                    -- Nhà cung cấp có hóa đơn
                    SELECT
                        si.partner_id AS partner_id,
                        si.currency_id AS currency_id
                    FROM supplier_invoice si

                    UNION

                    -- Nhà cung cấp có phiếu chi (Loại chi phí = Nhà cung cấp)
                    SELECT
                        apr.supplier_id AS partner_id,
                        COALESCE(apr.currency_id, rc.id) AS currency_id
                    FROM account_payment_request apr
                    JOIN res_company c ON c.id = 1
                    JOIN res_currency rc ON rc.id = c.currency_id
                    WHERE apr.receive_type = 'supplier'
                ) AS sub
                WHERE sub.partner_id IS NOT NULL
            )
            """ % self._table
        )

    # =====================================================
    # COMPUTE
    # =====================================================

    # ----- 1) Lấy danh sách hóa đơn theo NCC + tiền tệ -----
    @api.depends("partner_id", "currency_id")
    def _compute_invoice_ids(self):
        Invoice = self.env["supplier.invoice"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                rec.invoice_ids = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ])
            else:
                rec.invoice_ids = False

    # ----- 2) Lấy danh sách phiếu chi theo NCC + tiền tệ -----
    @api.depends("partner_id", "currency_id")
    def _compute_payment_request_ids(self):
        Payment = self.env["account.payment.request"]
        for rec in self:
            if not rec.partner_id:
                rec.payment_request_ids = False
                continue

            domain = [
                ("receive_type", "=", "supplier"),
                ("supplier_id", "=", rec.partner_id.id),
                ("state", "in", ("posted", "done", "paid")),
            ]
            if "currency_id" in Payment._fields and rec.currency_id:
                domain.append(("currency_id", "=", rec.currency_id.id))

            rec.payment_request_ids = Payment.search(domain)

    # ----- 3) Danh sách HỢP ĐỒNG NCC -----
    @api.depends("partner_id", "currency_id")
    def _compute_contract_ids(self):
        Contract = self.env["supplier.contract"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                rec.contract_ids = Contract.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ])
            elif rec.partner_id:
                rec.contract_ids = Contract.search([
                    ("partner_id", "=", rec.partner_id.id),
                ])
            else:
                rec.contract_ids = False

    def _inverse_contract_ids(self):
        for rec in self:
            for contract in rec.contract_ids:
                contract.partner_id = rec.partner_id

    def _inverse_invoice_ids(self):
        for rec in self:
            for invoice in rec.invoice_ids:
                invoice.partner_id = rec.partner_id

    def _inverse_payment_request_ids(self):
        for rec in self:
            for payment in rec.payment_request_ids:
                payment.supplier_id = rec.partner_id

    # ----- 4) Tổng giá trị HỢP ĐỒNG -----
    @api.depends("partner_id", "currency_id")
    def _compute_total_contract_amount(self):
        Contract = self.env["supplier.contract"]
        for rec in self:
            if not rec.partner_id:
                rec.total_contract_amount = 0.0
                continue

            domain = [("partner_id", "=", rec.partner_id.id)]
            if rec.currency_id:
                domain.append(("currency_id", "=", rec.currency_id.id))

            contracts = Contract.search(domain)
            rec.total_contract_amount = sum(contracts.mapped("amount")) if contracts else 0.0

    # ----- 5) Tổng giá trị HỒ SƠ QUYẾT TOÁN -----
    @api.depends("partner_id", "currency_id")
    def _compute_total_settlements_amount(self):
        Settlement = self.env["supplier.settlement"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                settlements = Settlement.search([
                    ("contract_id.partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ])
                rec.total_settlements_amount = sum(settlements.mapped("amount")) if settlements else 0.0
            else:
                rec.total_settlements_amount = 0.0

    # ----- 6) Tổng giá trị HÓA ĐƠN -----
    @api.depends("partner_id", "currency_id")
    def _compute_total_invoice_amount(self):
        Invoice = self.env["supplier.invoice"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                invoices = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ])
                rec.total_invoice_amount = sum(invoices.mapped("amount")) if invoices else 0.0
            else:
                rec.total_invoice_amount = 0.0

    # ----- 7) Tổng giá trị PHIẾU CHI -----
    @api.depends("partner_id", "currency_id")
    def _compute_total_payment_amount(self):
        Payment = self.env["account.payment.request"]

        amount_field = None
        if "total" in Payment._fields:
            amount_field = "total"
        else:
            for candidate in ["amount", "requested_amount", "amount_total", "paid_amount"]:
                if candidate in Payment._fields:
                    amount_field = candidate
                    break

        for rec in self:
            if not rec.partner_id or not amount_field:
                rec.total_payment_amount = 0.0
                continue

            pay_domain = [
                ("receive_type", "=", "supplier"),
                ("supplier_id", "=", rec.partner_id.id),
                ("state", "in", ("posted", "done", "paid")),
            ]
            if "currency_id" in Payment._fields and rec.currency_id:
                pay_domain.append(("currency_id", "=", rec.currency_id.id))

            payments = Payment.search(pay_domain)
            rec.total_payment_amount = sum(payments.mapped(amount_field)) if payments else 0.0

    # ----- 8) Còn nợ & Tạm ứng (tính cả công nợ cũ) -----
    @api.depends("total_invoice_amount", "total_payment_amount", "old_debt")
    def _compute_residual_and_advance(self):
        """
        Nghĩa vụ phải trả = Hóa đơn + Công nợ cũ
        So với Tổng phiếu chi:
          - Nếu phiếu chi < nghĩa vụ  => Còn nợ
          - Nếu phiếu chi > nghĩa vụ  => Tạm ứng
        """
        for rec in self:
            invoice_total = rec.total_invoice_amount or 0.0
            payment_total = rec.total_payment_amount or 0.0
            old = rec.old_debt or 0.0

            base = invoice_total + old  # tổng nghĩa vụ phải trả

            residual = base - payment_total
            rec.residual_amount = residual if residual > 0 else 0.0

            advance = payment_total - base
            rec.advance_amount = advance if advance > 0 else 0.0

    # ----- 9) Ngày đến hạn gần nhất & số ngày đến hạn -----
    @api.depends("partner_id", "currency_id")
    def _compute_due_date(self):
        Invoice = self.env["supplier.invoice"]
        today = date.today()

        for rec in self:
            if rec.partner_id and rec.currency_id:
                invoices = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                    ("due_date", "!=", False),
                ])
                if invoices:
                    nearest_due = min(invoices.mapped("due_date"))
                    rec.due_date = nearest_due

                    delta = (nearest_due - today).days
                    if delta > 0:
                        rec.due_days = f"Còn {delta} ngày - Tính từ {nearest_due.strftime('%d/%m/%Y')}"
                    elif delta == 0:
                        rec.due_days = f"Hôm nay - {nearest_due.strftime('%d/%m/%Y')}"
                    else:
                        rec.due_days = f"Quá hạn {abs(delta)} ngày - Tính từ {nearest_due.strftime('%d/%m/%Y')}"
                else:
                    rec.due_date = False
                    rec.due_days = "-"
            else:
                rec.due_date = False
                rec.due_days = "-"

    @api.depends("due_date")
    def _compute_due_days_html(self):
        today = date.today()
        for rec in self:
            if rec.due_date:
                delta = (rec.due_date - today).days
                date_str = rec.due_date.strftime("%d/%m/%Y")
                if delta > 3:
                    rec.due_days_html = (
                        f"<span style='color:green;font-weight:bold;'>"
                        f"Còn {delta} ngày - Tính từ {date_str}"
                        f"</span>"
                    )
                elif 0 < delta <= 3:
                    rec.due_days_html = (
                        f"<span style='color:orange;font-weight:bold;'>"
                        f"Sắp đến hạn ({delta} ngày) - {date_str}"
                        f"</span>"
                    )
                elif delta == 0:
                    rec.due_days_html = (
                        f"<span style='color:orange;font-weight:bold;'>"
                        f"Đến hạn hôm nay - {date_str}"
                        f"</span>"
                    )
                else:
                    rec.due_days_html = (
                        f"<span style='color:red;font-weight:bold;'>"
                        f"Quá hạn {abs(delta)} ngày - Tính từ {date_str}"
                        f"</span>"
                    )
            else:
                rec.due_days_html = "-"

    # ----- 10) Ghi chú / Diễn giải / Công nợ cũ -----
    @api.depends("partner_id", "currency_id")
    def _compute_note(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                note_rec = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.note = note_rec.note if note_rec else False
            else:
                rec.note = False

    def _inverse_note(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            note_rec = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if note_rec:
                note_rec.note = rec.note or False
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "note": rec.note or False,
                })

    @api.depends("partner_id", "currency_id")
    def _compute_interpretation(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                n = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.interpretation = n.interpretation or False if n else False
            else:
                rec.interpretation = False

    def _inverse_interpretation(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if n:
                n.interpretation = rec.interpretation or False
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "interpretation": rec.interpretation or False,
                })

    @api.depends("partner_id", "currency_id")
    def _compute_old_debt(self):
        """
        Công nợ cũ = old_debt trong note + tổng old_debt của các hợp đồng NCC đó.
        """
        Note = self.env["supplier.invoice.payment.summary.note"]
        Contract = self.env["supplier.contract"]

        for rec in self:
            if rec.partner_id and rec.currency_id:
                note_rec = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                note_old = note_rec.old_debt or 0.0 if note_rec else 0.0

                contracts = Contract.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ])
                contract_old = sum(contracts.mapped("old_debt")) if contracts else 0.0

                rec.old_debt = note_old + contract_old
            else:
                rec.old_debt = 0.0

    def _inverse_old_debt(self):
        """
        Khi sửa trực tiếp old_debt trên view tổng hợp:
        lưu lại vào note (phần công nợ cũ chung),
        còn old_debt từng hợp đồng giữ nguyên.
        """
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if n:
                n.old_debt = rec.old_debt or 0.0
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "old_debt": rec.old_debt or 0.0,
                })

    # ----- 11) Đối chiếu công nợ (checkbox) -----
    @api.depends("partner_id", "currency_id")
    def _compute_reconciled(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                n = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.reconciled = bool(n.reconciled) if n else False
            else:
                rec.reconciled = False

    def _inverse_reconciled(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            vals = {"reconciled": bool(rec.reconciled)}
            if n:
                n.write(vals)
            else:
                vals.update({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                })
                Note.create(vals)
    @api.depends("partner_id", "currency_id")
    def _compute_supplier_category(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                n = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.supplier_category = n.supplier_category or False if n else False
            else:
                rec.supplier_category = False
    def _inverse_supplier_category(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if n:
                n.supplier_category = rec.supplier_category or False
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "supplier_category": rec.supplier_category or False,
                })
    @api.depends("partner_id", "currency_id")
    def _compute_supplier_domestic_type(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                n = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.supplier_domestic_type = n.supplier_domestic_type or False if n else False
            else:
                rec.supplier_domestic_type = False
    def _inverse_supplier_domestic_type(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if n:
                n.supplier_domestic_type = rec.supplier_domestic_type or False
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "supplier_domestic_type": rec.supplier_domestic_type or False,
                })
    @api.depends("partner_id", "currency_id")
    def _compute_supply_category(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                n = Note.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                ], limit=1)
                rec.supply_category = n.supply_category.id if n and n.supply_category else False
            else:
                rec.supply_category = False
    def _inverse_supply_category(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue
            n = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)
            if n:
                n.supply_category = rec.supply_category.id if rec.supply_category else False
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "supply_category": rec.supply_category.id if rec.supply_category else False,
                })
    

class SupplierInvoicePaymentSummaryNote(models.Model):
    _name = "supplier.invoice.payment.summary.note"
    _description = "Ghi chú tổng hợp công nợ NCC (HĐ & phiếu chi)"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner",
        string="Nhà cung cấp",
        required=True,
        domain=[("supplier_rank", ">", 0)],
        ondelete="cascade",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Tiền tệ",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    old_debt = fields.Monetary(
        string="Công nợ cũ",
        currency_field="currency_id",
        help="Số tiền còn nợ trước đây, dùng riêng cho tổng hợp HĐ & phiếu chi.",
    )
    supplier_category = fields.Selection(
        [
            ("domestic", "NCC trong nước"),
            ("foreign", "NCC nước ngoài"),
        ],
        default="domestic",
        string="Loại nhà cung cấp",
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
    supply_category= fields.Many2one(
        "supplier.supply.category",
        string="Hạng mục cung cấp",
        help="Hạng mục cung cấp của nhà cung cấp.",
    )
    reconciled = fields.Boolean("Đã đối chiếu công nợ")
    note = fields.Text("Ghi chú")
    interpretation = fields.Char("Diễn giải")
    # 🔹 Checkbox lưu trạng thái đối chiếu
    
    _sql_constraints = [
        (
            "partner_currency_unique",
            "unique(partner_id, currency_id)",
            "Mỗi nhà cung cấp và tiền tệ chỉ có một ghi chú/công nợ cũ (HĐ & phiếu chi).",
        ),
    ]



class SupplierDebtRealReport(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_supplier_debt_real_view'
    _description = "Báo cáo Tổng hợp Công nợ NCC thực tế (theo hóa đơn)"

    @api.model
    def _get_report_values(self, docids, data=None):
        Invoice = self.env['supplier.invoice']
        Payment = self.env['account.payment.request']
        Company = self.env.company

        # ==============================
        # 1. LẤY DANH SÁCH HÓA ĐƠN
        # ==============================
        # Nếu in từ tree hóa đơn có chọn dòng -> dùng docids
        # Nếu in từ menu (docids=[0] hoặc rỗng) -> lấy tất cả hóa đơn
        if docids and docids != [0]:
            invoices = Invoice.browse(docids)
        else:
            invoices = Invoice.search([])

        if not invoices:
            # Không có dữ liệu => trả về context rỗng
            return {
                'done_domestic_labor': [],
                'done_domestic_material': [],
                'done_foreign': [],
                'pending_domestic_labor': [],
                'pending_domestic_material': [],
                'pending_foreign': [],
            }

        # ==============================
        # 2. XÁC ĐỊNH FIELD SỐ TIỀN TRÊN PHIẾU CHI
        # ==============================
        amount_field = None
        for candidate in ["total", "amount", "requested_amount", "amount_total", "paid_amount"]:
            if candidate in Payment._fields:
                amount_field = candidate
                break

        # Nếu không tìm được field tiền -> coi như không có phiếu chi
        payments = Payment.browse()
        if amount_field:
            # Chỉ lấy phiếu chi loại nhà cung cấp, đã hạch toán / thanh toán
            payments = Payment.search([
                ("receive_type", "=", "supplier"),
                ("state", "in", ("posted", "done", "paid")),
            ])

        # ==============================
        # 3. XÂY DỰNG NHÓM (group) THEO NCC
        #    key = (partner_id, currency_id, supplier_category, supplier_domestic_type, reconciled)
        # ==============================
        groups = {}
        today = date.today()
        company_currency = Company.currency_id

        def _get_currency(rec):
            return rec.currency_id or company_currency

        # --- 3.1. Gom hóa đơn ---
        for inv in invoices:
            if not inv.partner_id:
                continue

            partner = inv.partner_id
            currency = _get_currency(inv)

            supplier_category = inv.supplier_category or "domestic"  # mặc định trong nước
            supplier_domestic_type = inv.supplier_domestic_type or False
            supply_category = inv.supply_category
            reconciled = bool(inv.reconciled)

            key = (
                partner.id,
                currency.id,
                supplier_category,
                supplier_domestic_type,
                reconciled,
            )

            if key not in groups:
                groups[key] = {
                    "partner": partner,
                    "partner_name": partner.name or "",
                    "currency": currency,
                    "supplier_category": supplier_category,
                    "supplier_domestic_type": supplier_domestic_type,
                    "supply_category": supply_category,
                    "supply_category_name": supply_category.name if supply_category else "",
                    "reconciled": reconciled,

                    "contract_amount": 0.0,
                    "invoice_amount": 0.0,

                    "paid_hd": 0.0,
                    "advance_amount": 0.0,
                    "total_payment": 0.0,

                    "residual_amount": 0.0,
                    "temp_surplus": 0.0,

                    "due_date": None,
                    "due_days": "",
                    "note": "",  # nếu cần sau này có thể lấy note riêng
                }

            g = groups[key]

            # Tổng giá trị HĐ: cộng theo hóa đơn (có thể double nếu 1 HĐ nhiều HĐ mua)
            if inv.contract_id and inv.contract_id.amount:
                g["contract_amount"] += inv.contract_id.amount

            # Tổng giá trị hóa đơn
            g["invoice_amount"] += inv.amount or 0.0

            # Ngày đến hạn gần nhất
            inv_due = inv.due_date or inv.date
            if inv_due:
                if not g["due_date"] or inv_due < g["due_date"]:
                    g["due_date"] = inv_due

        # Chuẩn bị map invoice_id -> list key group chứa invoice đó
        invoice_ids = invoices.ids
        invoice_id_to_groups = {}
        for key, g in groups.items():
            partner = g["partner"]
            currency = g["currency"]
            supplier_category = g["supplier_category"]
            supplier_domestic_type = g["supplier_domestic_type"]
            reconciled = g["reconciled"]

            invs = invoices.filtered(
                lambda inv: inv.partner_id == partner
                            and _get_currency(inv) == currency
                            and (inv.supplier_category or "domestic") == supplier_category
                            and (inv.supplier_domestic_type or False) == supplier_domestic_type
                            and bool(inv.reconciled) == reconciled
            )
            for inv in invs:
                invoice_id_to_groups.setdefault(inv.id, set()).add(key)

        # --- 3.2. Gắn phiếu chi vào groups ---
        for pay in payments:
            if not pay.supplier_id:
                continue

            partner = pay.supplier_id
            currency = _get_currency(pay)
            amt = getattr(pay, amount_field) or 0.0

            # Lấy thông tin phân loại từ payment, nếu không có thì fallback từ invoice
            inv = pay.invoice_id if "invoice_id" in Payment._fields else False

            supplier_category = (
                getattr(pay, "supplier_category", False)
                or (inv.supplier_category if inv else False)
                or "domestic"
            )
            supplier_domestic_type = (
                getattr(pay, "supplier_domestic_type", False)
                or (inv.supplier_domestic_type if inv else False)
                or False
            )
            supply_category = (
                getattr(pay, "supply_category", False)
                or (inv.supply_category if inv else False)
                or False
            )

            if inv and inv.id in invoice_id_to_groups:
                # Phiếu chi đã gắn HĐ => dùng reconciled của HĐ để phân loại Đã/Chờ đối chiếu
                rec_flag = bool(inv.reconciled)
            else:
                # Phiếu chi chưa gắn HĐ => luôn xem là CHỜ ĐỐI CHIẾU
                rec_flag = False

            key = (
                partner.id,
                currency.id,
                supplier_category,
                supplier_domestic_type,
                rec_flag,
            )

            if key not in groups:
                # nhóm chỉ có phiếu chi (chưa có hóa đơn nhưng vẫn phải thể hiện NCC)
                groups[key] = {
                    "partner": partner,
                    "partner_name": partner.name or "",
                    "currency": currency,
                    "supplier_category": supplier_category,
                    "supplier_domestic_type": supplier_domestic_type,
                    "supply_category": supply_category,
                    "supply_category_name": supply_category.name if supply_category else "",
                    "reconciled": rec_flag,

                    "contract_amount": 0.0,
                    "invoice_amount": 0.0,

                    "paid_hd": 0.0,
                    "advance_amount": 0.0,
                    "total_payment": 0.0,

                    "residual_amount": 0.0,
                    "temp_surplus": 0.0,

                    "due_date": None,
                    "due_days": "",
                    "note": "",
                }

            g = groups[key]

            # supply_category: ưu tiên lấy cái có giá trị
            if supply_category and not g["supply_category"]:
                g["supply_category"] = supply_category
                g["supply_category_name"] = supply_category.name

            # Tổng chi
            g["total_payment"] += amt

            # Đã HĐ hay Chưa HĐ
            if inv and inv.id in invoice_id_to_groups:
                g["paid_hd"] += amt
            else:
                # phiếu chi chưa có hóa đơn => chi chưa HĐ / tạm ứng
                g["advance_amount"] += amt

        # ==============================
        # 4. TÍNH CÒN NỢ / TẠM ỨNG & HẠN THANH TOÁN
        # ==============================
        for key, g in groups.items():
            invoice_total = g["invoice_amount"] or 0.0
            total_payment = (g["total_payment"] or 0.0)

            # Còn nợ / Tạm ứng (không dùng công nợ cũ ở report này)
            residual = invoice_total - total_payment
            temp_surplus = total_payment - invoice_total

            g["residual_amount"] = residual if residual > 0 else 0.0
            g["temp_surplus"] = temp_surplus if temp_surplus > 0 else 0.0

            # Hạn thanh toán dưới dạng text
            due = g["due_date"]
            if due:
                delta = (due - today).days
                if delta > 0:
                    g["due_days"] = f"Còn {delta} ngày từ {due.strftime('%d/%m/%Y')}"
                elif delta == 0:
                    g["due_days"] = f"Đến hạn hôm nay - {due.strftime('%d/%m/%Y')}"
                else:
                    g["due_days"] = f"Quá hạn {abs(delta)} ngày từ {due.strftime('%d/%m/%Y')}"
            else:
                g["due_days"] = ""

        # ==============================
        # 5. LỌC BỎ DÒNG residual = 0 & temp_surplus = 0
        # ==============================
        def _filter_zero(lst):
            res = []
            for l in lst:
                if (l.get("residual_amount") or 0.0) != 0.0 or (l.get("temp_surplus") or 0.0) != 0.0:
                    res.append(l)
            return res

        # ==============================
        # 6. CHIA 6 NHÓM THEO YÊU CẦU
        # ==============================
        done_domestic_labor = []
        done_domestic_material = []
        done_foreign = []

        pending_domestic_labor = []
        pending_domestic_material = []
        pending_foreign = []

        for key, g in groups.items():
            supplier_category = g["supplier_category"]        # 'domestic' / 'foreign'
            domestic_type = g["supplier_domestic_type"]       # 'labor' / 'material_service' / False
            is_reconciled = g["reconciled"]                   # True / False

            if supplier_category == "foreign":
                if is_reconciled:
                    done_foreign.append(g)
                else:
                    pending_foreign.append(g)
            else:  # domestic
                # nếu không set, coi là vật tư, dịch vụ
                if domestic_type == "labor":
                    if is_reconciled:
                        done_domestic_labor.append(g)
                    else:
                        pending_domestic_labor.append(g)
                else:
                    if is_reconciled:
                        done_domestic_material.append(g)
                    else:
                        pending_domestic_material.append(g)

        # Lọc bỏ dòng 0/0
        done_domestic_labor = _filter_zero(done_domestic_labor)
        done_domestic_material = _filter_zero(done_domestic_material)
        done_foreign = _filter_zero(done_foreign)

        pending_domestic_labor = _filter_zero(pending_domestic_labor)
        pending_domestic_material = _filter_zero(pending_domestic_material)
        pending_foreign = _filter_zero(pending_foreign)

        # Sắp xếp danh sách theo tên NCC
        key_name = lambda l: (l.get("partner_name") or "").lower()

        done_domestic_labor = sorted(done_domestic_labor, key=key_name)
        done_domestic_material = sorted(done_domestic_material, key=key_name)
        done_foreign = sorted(done_foreign, key=key_name)

        pending_domestic_labor = sorted(pending_domestic_labor, key=key_name)
        pending_domestic_material = sorted(pending_domestic_material, key=key_name)
        pending_foreign = sorted(pending_foreign, key=key_name)

        # ==============================
        # 7. TRẢ VỀ CHO TEMPLATE QWEB
        # ==============================
        return {
            "done_domestic_labor": done_domestic_labor,
            "done_domestic_material": done_domestic_material,
            "done_foreign": done_foreign,

            "pending_domestic_labor": pending_domestic_labor,
            "pending_domestic_material": pending_domestic_material,
            "pending_foreign": pending_foreign,
        }
class SupplierInvoiceListReport(models.AbstractModel):
    _name = "report.vendor_debt_management.report_supplier_invoice_list"
    _description = "Báo cáo danh sách hóa đơn NCC"

    def _get_report_values(self, docids, data=None):
        data = data or {}

        # Hóa đơn nhận từ wizard qua docids
        invoices = self.env["supplier.invoice"].browse(docids)

        total_untaxed = sum(invoices.mapped("amount_untaxed"))
        total_tax = sum(invoices.mapped("amount_tax"))
        total_amount = sum(invoices.mapped("amount"))

        return {
            "doc_ids": invoices.ids,
            "doc_model": "supplier.invoice",
            "docs": invoices,

            "filter_type": data.get("filter_type"),
            "date_from": data.get("date_from"),
            "date_to": data.get("date_to"),
            "year": data.get("year"),
            "month": data.get("month"),
            "quarter": data.get("quarter"),
            "group_by": data.get("group_by"),

            "total_untaxed": total_untaxed,
            "total_tax": total_tax,
            "total_amount": total_amount,
        }