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
    note = fields.Text("Ghi chú")
    interpretation = fields.Char("Diễn giải")
    # 🔹 Checkbox lưu trạng thái đối chiếu
    reconciled = fields.Boolean("Đã đối chiếu công nợ")
    
    _sql_constraints = [
        (
            "partner_currency_unique",
            "unique(partner_id, currency_id)",
            "Mỗi nhà cung cấp và tiền tệ chỉ có một ghi chú/công nợ cũ (HĐ & phiếu chi).",
        ),
    ]


class ReportSupplierSummary(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_supplier_summary_view'
    _description = 'Supplier Summary Report'

    def _get_report_values(self, docids, data=None):
        Summary = self.env['supplier.invoice.payment.summary']

        docs_all = Summary.search([])

        docs = docs_all.filtered(
            lambda r: (r.residual_amount or 0.0) != 0.0
                      or (r.advance_amount or 0.0) != 0.0
        )

        return {
            'doc_ids': docs.ids,
            'doc_model': 'supplier.invoice.payment.summary',
            'docs': docs,
        }
class SupplierDebtRealReport(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_supplier_debt_real_view'
    _description = "Báo cáo Tổng hợp Công nợ NCC thực tế"

    @api.model
    def _get_report_values(self, docids, data=None):
        Summary = self.env['supplier.invoice.payment.summary']

        # 1. Lấy dữ liệu gốc
        # Nếu in từ danh sách có chọn dòng -> dùng docids
        # Nếu in từ act_url với /0 -> lấy toàn bộ
        if docids and docids != [0]:
            records = Summary.browse(docids)
        else:
            records = Summary.search([])

        # 2. Tạo các nhóm rỗng (recordset rỗng)
        empty = Summary.browse()
        domestic_labor_done = empty
        domestic_material_done = empty
        foreign_done = empty

        domestic_labor_wait = empty
        domestic_material_wait = empty
        foreign_wait = empty

        # 3. Phân loại thủ công theo từng dòng
        for rec in records:
            # Truy cập field compute => Odoo tự gọi @api.depends
            category = rec.supplier_category           # 'domestic' / 'foreign'
            domestic_type = rec.supplier_domestic_type # 'labor' / 'material_service' / False
            is_reconciled = bool(rec.reconciled)       # True / False

            if category == 'foreign':
                # NCC nước ngoài => không chia nhân công / vật tư
                if is_reconciled:
                    foreign_done |= rec
                else:
                    foreign_wait |= rec

            elif category == 'domestic':
                # NCC trong nước => chia thêm nhóm nhân công / vật tư
                if domestic_type == 'labor':
                    if is_reconciled:
                        domestic_labor_done |= rec
                    else:
                        domestic_labor_wait |= rec
                elif domestic_type == 'material_service':
                    if is_reconciled:
                        domestic_material_done |= rec
                    else:
                        domestic_material_wait |= rec
                else:
                    # nếu chưa chọn loại, tạm đẩy về nhóm Vật tư & dịch vụ
                    if is_reconciled:
                        domestic_material_done |= rec
                    else:
                        domestic_material_wait |= rec

        # 4. Sắp xếp từng nhóm theo tên NCC
        keyfunc = lambda r: (r.partner_id.name or '').lower()

        domestic_labor_done = domestic_labor_done.sorted(key=keyfunc)
        domestic_material_done = domestic_material_done.sorted(key=keyfunc)
        foreign_done = foreign_done.sorted(key=keyfunc)

        domestic_labor_wait = domestic_labor_wait.sorted(key=keyfunc)
        domestic_material_wait = domestic_material_wait.sorted(key=keyfunc)
        foreign_wait = foreign_wait.sorted(key=keyfunc)

        # 5. Trả về biến cho QWeb template
        return {
            "domestic_labor_done": domestic_labor_done,
            "domestic_material_done": domestic_material_done,
            "foreign_done": foreign_done,

            "domestic_labor_wait": domestic_labor_wait,
            "domestic_material_wait": domestic_material_wait,
            "foreign_wait": foreign_wait,
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