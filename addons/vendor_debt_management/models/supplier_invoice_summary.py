# -*- coding: utf-8 -*-
from odoo import models, fields, api, tools
from datetime import date
import secrets


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

    contract_ids = fields.One2many(
        "supplier.contract",
        compute="_compute_contract_ids",
        inverse="_inverse_contract_ids",
        string="Hợp đồng NCC",
    )

    due_date = fields.Date("Ngày đến hạn", compute="_compute_due_date")
    due_days = fields.Char("Số ngày đến hạn", compute="_compute_due_date")
    due_days_html = fields.Html(
        "Số ngày đến hạn (màu)",
        compute="_compute_due_days_html",
        sanitize=False,
    )

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

    # ========== SHARE INFO ==========
    # Không lưu trực tiếp trên model _auto=False
    share_token = fields.Char(
        string="Share Token",
        compute="_compute_share_info",
        inverse="_inverse_share_info",
        store=False,
    )
    share_enabled = fields.Boolean(
        string="Cho phép chia sẻ",
        compute="_compute_share_info",
        inverse="_inverse_share_info",
        store=False,
    )
    share_expired_at = fields.Datetime(
        string="Hết hạn chia sẻ",
        compute="_compute_share_info",
        inverse="_inverse_share_info",
        store=False,
    )
    share_url = fields.Char(
        string="Link chia sẻ",
        compute="_compute_share_url",
        store=False,
    )

    # =====================================================
    # SHARE ACTIONS
    # =====================================================
    @api.depends("partner_id", "currency_id")
    def _compute_share_info(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            rec.share_token = False
            rec.share_enabled = False
            rec.share_expired_at = False

            if not (rec.partner_id and rec.currency_id):
                continue

            note = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)

            if note:
                rec.share_token = note.share_token or False
                rec.share_enabled = bool(note.share_enabled)
                rec.share_expired_at = note.share_expired_at or False

    def _inverse_share_info(self):
        Note = self.env["supplier.invoice.payment.summary.note"]
        for rec in self:
            if not (rec.partner_id and rec.currency_id):
                continue

            note = Note.search([
                ("partner_id", "=", rec.partner_id.id),
                ("currency_id", "=", rec.currency_id.id),
            ], limit=1)

            vals = {
                "share_token": rec.share_token or False,
                "share_enabled": bool(rec.share_enabled),
                "share_expired_at": rec.share_expired_at or False,
            }

            if note:
                note.write(vals)
            else:
                vals.update({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                })
                Note.create(vals)

    @api.depends("share_token")
    def _compute_share_url(self):
        for rec in self:
            rec.share_url = rec.get_share_url() or False

    def action_generate_share_link(self):
        self.ensure_one()

        if not self.partner_id or not self.currency_id:
            return False

        Note = self.env["supplier.invoice.payment.summary.note"]
        note = Note.search([
            ("partner_id", "=", self.partner_id.id),
            ("currency_id", "=", self.currency_id.id),
        ], limit=1)

        if not note:
            note = Note.create({
                "partner_id": self.partner_id.id,
                "currency_id": self.currency_id.id,
            })

        if not note.share_token:
            note.share_token = secrets.token_urlsafe(32)

        note.share_enabled = True

        url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/vendor-debt/share/{note.share_token}"
        return {
            "url": url,
            "share_url": url,
        }


    def action_regenerate_share_link(self):
        self.ensure_one()

        if not self.partner_id or not self.currency_id:
            return False

        Note = self.env["supplier.invoice.payment.summary.note"]
        note = Note.search([
            ("partner_id", "=", self.partner_id.id),
            ("currency_id", "=", self.currency_id.id),
        ], limit=1)

        if not note:
            note = Note.create({
                "partner_id": self.partner_id.id,
                "currency_id": self.currency_id.id,
            })

        note.share_token = secrets.token_urlsafe(32)
        note.share_enabled = True

        url = f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/vendor-debt/share/{note.share_token}"
        return {
            "url": url,
            "share_url": url,
        }


    def get_share_url(self):
        self.ensure_one()

        if not self.partner_id or not self.currency_id:
            return False

        note = self.env["supplier.invoice.payment.summary.note"].search([
            ("partner_id", "=", self.partner_id.id),
            ("currency_id", "=", self.currency_id.id),
        ], limit=1)

        if not note or not note.share_token:
            return False

        return f"{self.env['ir.config_parameter'].sudo().get_param('web.base.url')}/vendor-debt/share/{note.share_token}"

    # =====================================================
    # ACTIONS
    # =====================================================
    def action_open_invoices(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        ctx.update({
            "default_partner_id": self.partner_id.id,
            "default_currency_id": self.currency_id.id,
            "search_default_partner_id": self.partner_id.id,
            "search_default_currency_id": self.currency_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn nhà cung cấp",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "domain": [
                ("partner_id", "=", self.partner_id.id),
                ("currency_id", "=", self.currency_id.id),
                ("no_payment", "=", False),
            ],
            "context": ctx,
        }

    def action_open_contracts(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        ctx.update({
            "default_partner_id": self.partner_id.id,
            "default_currency_id": self.currency_id.id,
            "search_default_partner_id": self.partner_id.id,
            "search_default_currency_id": self.currency_id.id,
        })
        return {
            "type": "ir.actions.act_window",
            "name": "Hợp đồng nhà cung cấp",
            "res_model": "supplier.contract",
            "view_mode": "tree,form",
            "domain": [
                ("partner_id", "=", self.partner_id.id),
                ("currency_id", "=", self.currency_id.id),
            ],
            "context": ctx,
        }

    def action_open_payments(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        ctx.update({
            "default_receive_type": "supplier",
            "default_supplier_id": self.partner_id.id,
            "default_currency_id": self.currency_id.id,
            "search_default_supplier_id": self.partner_id.id,
        })
        domain = [
            ("receive_type", "=", "supplier"),
            ("supplier_id", "=", self.partner_id.id),
        ]
        if "currency_id" in self.env["account.payment.request"]._fields and self.currency_id:
            domain.append(("currency_id", "=", self.currency_id.id))

        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu chi nhà cung cấp",
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "domain": domain,
            "context": ctx,
        }

    @api.model
    def get_supplier_debt_real_report_data(self):
        Report = self.env["report.vendor_debt_management.report_supplier_debt_real_view"]
        Summary = self.env["supplier.invoice.payment.summary"]

        data = Report._get_report_values([0], data=None)

        def _extract_id(value):
            if not value:
                return False
            if isinstance(value, int):
                return value
            if hasattr(value, "id"):
                return value.id
            if isinstance(value, (list, tuple)) and value:
                return value[0]
            return False

        def _attach_summary_id(rows):
            result = []
            for row in rows or []:
                row = dict(row)

                partner_id = row.get("partner_id") or _extract_id(row.get("partner"))
                currency_id = row.get("currency_id") or _extract_id(row.get("currency"))

                summary = False
                if partner_id and currency_id:
                    summary = Summary.search([
                        ("partner_id", "=", partner_id),
                        ("currency_id", "=", currency_id),
                    ], limit=1)

                row["summary_id"] = summary.id if summary else False
                row["partner_id"] = partner_id or False
                row["currency_id"] = currency_id or False

                result.append(row)
            return result

        return {
            "done_domestic_labor": _attach_summary_id(data.get("done_domestic_labor", [])),
            "done_domestic_material": _attach_summary_id(data.get("done_domestic_material", [])),
            "done_foreign": _attach_summary_id(data.get("done_foreign", [])),
            "pending_domestic_labor": _attach_summary_id(data.get("pending_domestic_labor", [])),
            "pending_domestic_material": _attach_summary_id(data.get("pending_domestic_material", [])),
            "pending_foreign": _attach_summary_id(data.get("pending_foreign", [])),
        }

    # =====================================================
    # SQL VIEW
    # =====================================================
    def init(self):
        """
        account_payment_request không có company_id.
        - Nếu apr.currency_id có => dùng luôn
        - Nếu apr.currency_id NULL => fallback currency công ty id=1
        """
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
                    WHERE si.partner_id IS NOT NULL
                      AND si.currency_id IS NOT NULL

                    UNION

                    -- Nhà cung cấp có phiếu chi
                    SELECT
                        apr.supplier_id AS partner_id,
                        COALESCE(apr.currency_id, rc.id) AS currency_id
                    FROM account_payment_request apr
                    JOIN res_company c ON c.id = 1
                    JOIN res_currency rc ON rc.id = c.currency_id
                    WHERE apr.receive_type = 'supplier'
                      AND apr.supplier_id IS NOT NULL
                ) AS sub
            )
            """ % self._table
        )

    # =====================================================
    # COMPUTE
    # =====================================================
    @api.depends("partner_id", "currency_id")
    def _compute_invoice_ids(self):
        Invoice = self.env["supplier.invoice"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                rec.invoice_ids = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                    ("no_payment", "=", False),
                ])
            else:
                rec.invoice_ids = False

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
                rec.contract_ids = Contract.search([("partner_id", "=", rec.partner_id.id)])
            else:
                rec.contract_ids = False

    def _inverse_contract_ids(self):
        for rec in self:
            for contract in rec.contract_ids:
                if rec.partner_id and "partner_id" in contract._fields:
                    contract.partner_id = rec.partner_id
                if rec.currency_id and "currency_id" in contract._fields:
                    contract.currency_id = rec.currency_id

    def _inverse_invoice_ids(self):
        for rec in self:
            for invoice in rec.invoice_ids:
                if rec.partner_id and "partner_id" in invoice._fields:
                    invoice.partner_id = rec.partner_id
                if rec.currency_id and "currency_id" in invoice._fields:
                    invoice.currency_id = rec.currency_id

    def _inverse_payment_request_ids(self):
        for rec in self:
            for payment in rec.payment_request_ids:
                if rec.partner_id and "supplier_id" in payment._fields:
                    payment.supplier_id = rec.partner_id
                if "receive_type" in payment._fields:
                    payment.receive_type = "supplier"
                if rec.currency_id and "currency_id" in payment._fields:
                    payment.currency_id = rec.currency_id

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

    @api.depends("partner_id", "currency_id")
    def _compute_total_invoice_amount(self):
        Invoice = self.env["supplier.invoice"]
        for rec in self:
            if rec.partner_id and rec.currency_id:
                invoices = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                    ("no_payment", "=", False),
                ])
                rec.total_invoice_amount = sum(invoices.mapped("amount")) if invoices else 0.0
            else:
                rec.total_invoice_amount = 0.0

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

    @api.depends("total_invoice_amount", "total_payment_amount", "old_debt")
    def _compute_residual_and_advance(self):
        for rec in self:
            invoice_total = rec.total_invoice_amount or 0.0
            payment_total = rec.total_payment_amount or 0.0
            old = rec.old_debt or 0.0

            base = invoice_total + old
            residual = base - payment_total
            rec.residual_amount = residual if residual > 0 else 0.0

            advance = payment_total - base
            rec.advance_amount = advance if advance > 0 else 0.0

    @api.depends("partner_id", "currency_id", "residual_amount")
    def _compute_due_date(self):
        Invoice = self.env["supplier.invoice"]
        today = date.today()

        for rec in self:
            if (rec.residual_amount or 0.0) <= 0.0:
                rec.due_date = False
                rec.due_days = ""
                continue

            if rec.partner_id and rec.currency_id:
                invoices = Invoice.search([
                    ("partner_id", "=", rec.partner_id.id),
                    ("currency_id", "=", rec.currency_id.id),
                    ("due_date", "!=", False),
                    ("no_payment", "=", False),
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
                    rec.due_days = ""
            else:
                rec.due_date = False
                rec.due_days = ""

    @api.depends("due_date", "residual_amount")
    def _compute_due_days_html(self):
        today = date.today()
        for rec in self:
            if (rec.residual_amount or 0.0) <= 0.0:
                rec.due_days_html = ""
                continue

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
                rec.due_days_html = ""

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
                rec.interpretation = (n.interpretation or False) if n else False
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
                rec.supplier_category = (n.supplier_category or "domestic") if n else "domestic"
            else:
                rec.supplier_category = "domestic"

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
                n.supplier_category = rec.supplier_category or "domestic"
            else:
                Note.create({
                    "partner_id": rec.partner_id.id,
                    "currency_id": rec.currency_id.id,
                    "supplier_category": rec.supplier_category or "domestic",
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
                rec.supplier_domestic_type = (n.supplier_domestic_type or False) if n else False
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
                rec.supply_category = n.supply_category if (n and n.supply_category) else False
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
                n.supply_category = rec.supply_category or False
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
        [("domestic", "NCC trong nước"), ("foreign", "NCC nước ngoài")],
        default="domestic",
        string="Loại nhà cung cấp",
        help="Phân loại nhà cung cấp: trong nước hoặc nước ngoài.",
    )
    supplier_domestic_type = fields.Selection(
        [("labor", "NCC Nhân công"), ("material_service", "NCC Vật tư, dịch vụ")],
        string="Nhóm NCC trong nước",
        help="Áp dụng khi Loại NCC là 'NCC trong nước'.",
    )
    supply_category = fields.Many2one("supplier.supply.category", string="Hạng mục cung cấp")
    reconciled = fields.Boolean("Đã đối chiếu công nợ")
    note = fields.Text("Ghi chú")
    interpretation = fields.Char("Diễn giải")

    # share fields lưu ở model thật
    share_token = fields.Char("Share Token", copy=False, index=True)
    share_enabled = fields.Boolean("Cho phép chia sẻ", default=False)
    share_expired_at = fields.Datetime("Hết hạn chia sẻ")

    _sql_constraints = [
        (
            "partner_currency_unique",
            "unique(partner_id, currency_id)",
            "Mỗi nhà cung cấp và tiền tệ chỉ có một ghi chú/công nợ cũ (HĐ & phiếu chi).",
        ),
    ]


class SupplierDebtRealReport(models.AbstractModel):
    _name = "report.vendor_debt_management.report_supplier_debt_real_view"
    _description = "Báo cáo Tổng hợp Công nợ NCC thực tế (theo hóa đơn) - gộp 1 NCC / 1 dòng"

    @api.model
    def _get_report_values(self, docids, data=None):
        Invoice = self.env["supplier.invoice"]
        Payment = self.env["account.payment.request"]
        Note = self.env["supplier.invoice.payment.summary.note"]
        Summary = self.env["supplier.invoice.payment.summary"]
        Company = self.env.company

        # ==============================
        # 1) LẤY HÓA ĐƠN
        # ==============================
        if docids and docids != [0]:
            invoices = Invoice.browse(docids).filtered(lambda x: not x.no_payment)
        else:
            invoices = Invoice.search([("no_payment", "=", False)])

        # ==============================
        # 2) FIELD SỐ TIỀN TRÊN PHIẾU CHI
        # ==============================
        amount_field = None
        for candidate in ["total", "amount", "requested_amount", "amount_total", "paid_amount"]:
            if candidate in Payment._fields:
                amount_field = candidate
                break

        today = date.today()
        company_currency = Company.currency_id

        def _get_currency(rec):
            return rec.currency_id or company_currency

        supplier_ids_in_scope = invoices.mapped("partner_id").ids if invoices else []

        payments = Payment.browse()
        if amount_field:
            pay_domain = [
                ("receive_type", "=", "supplier"),
                ("state", "in", ("posted", "done", "paid")),
            ]
            if docids and docids != [0] and supplier_ids_in_scope:
                pay_domain.append(("supplier_id", "in", supplier_ids_in_scope))
            payments = Payment.search(pay_domain)

        # ==============================
        # 3) GROUP (partner_id, currency_id)
        # ==============================
        groups = {}
        sc_names_by_key = {}

        def _ensure_group(partner, currency):
            key = (partner.id, currency.id)
            if key not in groups:
                groups[key] = {
                    "partner": partner,
                    "partner_name": partner.name or "",
                    "currency": currency,
                    "supplier_category": "domestic",
                    "supplier_domestic_type": False,
                    "supply_category_name": "",
                    "reconciled": False,
                    "contract_amount": 0.0,
                    "invoice_amount": 0.0,
                    "paid_hd": 0.0,
                    "advance_amount": 0.0,
                    "total_payment": 0.0,
                    "residual_amount": 0.0,
                    "due_date": None,
                    "due_days": "",
                }
                sc_names_by_key[key] = set()
            return key, groups[key]

        # --- 3.1) Gom hóa đơn ---
        for inv in invoices:
            if not inv.partner_id:
                continue
            partner = inv.partner_id
            currency = _get_currency(inv)
            key, g = _ensure_group(partner, currency)

            g["invoice_amount"] += inv.amount or 0.0

            sc = getattr(inv, "supply_category", False)
            if sc and sc.name:
                sc_names_by_key[key].add(sc.name)

        # --- 3.2) Gom phiếu chi ---
        for pay in payments:
            if not pay.supplier_id:
                continue

            inv = pay.invoice_id if "invoice_id" in Payment._fields else False
            if inv and getattr(inv, "no_payment", False):
                continue

            partner = pay.supplier_id
            currency = _get_currency(pay)
            key, g = _ensure_group(partner, currency)

            amt = getattr(pay, amount_field) or 0.0
            g["total_payment"] += amt

            if inv:
                g["paid_hd"] += amt
            else:
                g["advance_amount"] += amt

            sc = getattr(pay, "supply_category", False)
            if sc and sc.name:
                sc_names_by_key[key].add(sc.name)

        if not groups:
            return {
                "done_domestic_labor": [],
                "done_domestic_material": [],
                "done_foreign": [],
                "pending_domestic_labor": [],
                "pending_domestic_material": [],
                "pending_foreign": [],
            }

        partner_ids = list({k[0] for k in groups.keys()})
        currency_ids = list({k[1] for k in groups.keys()})

        # ==============================
        # 4) NOTE + SUMMARY MAP
        # ==============================
        notes = Note.search([
            ("partner_id", "in", partner_ids),
            ("currency_id", "in", currency_ids),
        ])
        note_map = {(n.partner_id.id, n.currency_id.id): n for n in notes}

        summaries = Summary.search([
            ("partner_id", "in", partner_ids),
            ("currency_id", "in", currency_ids),
        ])
        summary_map = {(s.partner_id.id, s.currency_id.id): s for s in summaries}

        # ==============================
        # 5) LẤY TỔNG HĐ TỪ SUMMARY.total_contract_amount
        # ==============================
        for key, g in groups.items():
            s = summary_map.get(key)

            if not s:
                s = Summary.search([
                    ("partner_id", "=", key[0]),
                    ("currency_id", "=", key[1]),
                ], limit=1)

            g["contract_amount"] = (s.total_contract_amount or 0.0) if s else 0.0

            if s and key not in summary_map:
                summary_map[key] = s

        # ==============================
        # 6) TÍNH CÒN NỢ + HẠN (theo SUMMARY) + PHÂN LOẠI
        # ==============================
        for key, g in groups.items():
            residual = (g["invoice_amount"] or 0.0) - (g["total_payment"] or 0.0)
            g["residual_amount"] = residual if residual > 0 else 0.0

            s = summary_map.get(key)

            if (g["residual_amount"] or 0.0) <= 0.0:
                g["due_date"] = None
                g["due_days"] = ""
            else:
                g["due_date"] = s.due_date if s else None
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

            n = note_map.get(key)
            if n:
                g["supplier_category"] = n.supplier_category or "domestic"
                g["supplier_domestic_type"] = n.supplier_domestic_type or False
                g["reconciled"] = bool(n.reconciled)

                if n.supply_category and n.supply_category.name:
                    g["supply_category_name"] = n.supply_category.name
                else:
                    names = sorted(sc_names_by_key.get(key) or [])
                    g["supply_category_name"] = ", ".join(names) if names else ""
            else:
                if s:
                    g["reconciled"] = bool(getattr(s, "reconciled", False))
                    g["supplier_category"] = (getattr(s, "supplier_category", False) or "domestic")
                    g["supplier_domestic_type"] = (getattr(s, "supplier_domestic_type", False) or False)

                    if getattr(s, "supply_category", False) and s.supply_category.name:
                        g["supply_category_name"] = s.supply_category.name
                    else:
                        names = sorted(sc_names_by_key.get(key) or [])
                        g["supply_category_name"] = ", ".join(names) if names else ""
                else:
                    g["reconciled"] = False
                    g["supplier_category"] = "domestic"
                    g["supplier_domestic_type"] = False
                    names = sorted(sc_names_by_key.get(key) or [])
                    g["supply_category_name"] = ", ".join(names) if names else ""

        def _keep(g):
            return (g.get("residual_amount") or 0.0) != 0.0 or (g.get("advance_amount") or 0.0) != 0.0

        rows = [g for g in groups.values() if _keep(g)]

        done_domestic_labor, done_domestic_material, done_foreign = [], [], []
        pending_domestic_labor, pending_domestic_material, pending_foreign = [], [], []

        for g in rows:
            supplier_category = g["supplier_category"] or "domestic"
            domestic_type = g["supplier_domestic_type"] or False
            is_reconciled = bool(g["reconciled"])

            if supplier_category == "foreign":
                (done_foreign if is_reconciled else pending_foreign).append(g)
            else:
                if domestic_type == "labor":
                    (done_domestic_labor if is_reconciled else pending_domestic_labor).append(g)
                else:
                    (done_domestic_material if is_reconciled else pending_domestic_material).append(g)

        key_name = lambda l: (l.get("partner_name") or "").lower()
        done_domestic_labor = sorted(done_domestic_labor, key=key_name)
        done_domestic_material = sorted(done_domestic_material, key=key_name)
        done_foreign = sorted(done_foreign, key=key_name)

        pending_domestic_labor = sorted(pending_domestic_labor, key=key_name)
        pending_domestic_material = sorted(pending_domestic_material, key=key_name)
        pending_foreign = sorted(pending_foreign, key=key_name)

        return {
            "done_domestic_labor": done_domestic_labor,
            "done_domestic_material": done_domestic_material,
            "done_foreign": done_foreign,
            "pending_domestic_labor": pending_domestic_labor,
            "pending_domestic_material": pending_domestic_material,
            "pending_foreign": pending_foreign,
        }