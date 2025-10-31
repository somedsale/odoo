from odoo import models, fields, api, tools
from datetime import date

class SupplierSummary(models.Model):
    _name = "supplier.summary"
    _description = "Tổng hợp công nợ nhà cung cấp"
    _auto = False
    _rec_name="partner_id"
    partner_id = fields.Many2one("res.partner", string="Nhà cung cấp", domain=[("supplier_rank", ">", 0)])
    contract_ids = fields.One2many(
        "supplier.contract",
        compute="_compute_contract_ids",
        inverse="_inverse_contract_ids",
        string="Hợp đồng"
    )
    due_date = fields.Date("Ngày đến hạn" , compute="_compute_due_date")
    due_days = fields.Char("Số ngày đến hạn", compute="_compute_due_date")
    total_contracts = fields.Monetary("Tổng giá trị hợp đồng", compute="_compute_total_contracts")
    total_invoices = fields.Monetary("Tổng giá trị hóa đơn", compute="_compute_total_invoices", currency_field="currency_id")
    paid_amount = fields.Monetary("Tổng giá trị đã thanh toán", compute="_compute_paid_amount", currency_field="currency_id")
    residual_amount = fields.Monetary("Còn nợ", compute="_compute_residual", currency_field="currency_id")
    advance_amount = fields.Monetary("Số tiền đã tạm ứng/ chưa hóa đơn", compute="_compute_advance_amount", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ")
    total_settlements = fields.Monetary("Tổng giá trị hồ sơ quyết toán", compute="_compute_total_settlements", currency_field="currency_id")
    # THAY field note cũ (nếu là simple Text) bằng field có compute + inverse
    note = fields.Text(
        "Ghi chú",
        compute="_compute_note",
        inverse="_inverse_note",
        store=False,
    )
    old_debt = fields.Monetary(
        string="Công nợ cũ",
        currency_field="currency_id",
        compute="_compute_old_debts",
        store=False,
        help="Số tiền còn nợ trước đây, sẽ cộng vào Còn nợ hiện tại."
    )
        # NEW: field người dùng nhập để ghi đè diễn giải
    interpretation = fields.Char(
        "Diễn giải",
        compute="_compute_interpretation",
        inverse="_inverse_interpretation",
        store=False,
    )
    def init(self):
        """Create or update the database view for supplier.summary."""
        tools.drop_view_if_exists(self.env.cr, self._table)  # Drop the view if it exists
        self.env.cr.execute("""
           CREATE OR REPLACE VIEW supplier_summary AS (
            SELECT
                row_number() OVER () AS id,
                sc.partner_id AS partner_id,
                sc.currency_id AS currency_id
            FROM supplier_contract sc
            GROUP BY sc.partner_id, sc.currency_id
            )
        """)
    due_days_html = fields.Html("Số ngày đến hạn", compute="_compute_due_days_html", sanitize=False)

    @api.depends("contract_ids.due_date")
    def _compute_due_days_html(self):
        today = date.today()
        for rec in self:
            if rec.due_date:
                delta = (rec.due_date - today).days
                if delta > 3:
                    rec.due_days_html = f"<span style='color:green;font-weight:bold;'>Còn {delta} ngày - Tính từ {rec.due_date.strftime('%d/%m/%Y')}</span>"
                elif delta > 0 and delta < 4:
                    rec.due_days_html = f"<span style='color:orange;font-weight:bold;'>Đến hạn hôm nay - {rec.due_date.strftime('%d/%m/%Y')}</span>"
                else:
                    rec.due_days_html = f"<span style='color:red;font-weight:bold;'>Quá hạn {abs(delta)} ngày - Tính từ {rec.due_date.strftime('%d/%m/%Y')}</span>"
            else:
                rec.due_days_html = "-"
    @api.depends("contract_ids.total_invoices")
    def _compute_total_invoices(self):
        for record in self:
            record.total_invoices = sum(record.contract_ids.mapped("total_invoices"))
    @api.depends("contract_ids.paid_amount")
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(record.contract_ids.mapped("paid_amount"))
    @api.depends("contract_ids.old_debt")
    def _compute_old_debts(self):
        for record in self:
            record.old_debt = sum(record.contract_ids.mapped("old_debt"))
    @api.depends("contract_ids.residual_amount", "old_debt")
    def _compute_residual(self):
        for record in self:
            current_residual = sum(record.contract_ids.mapped("residual_amount"))
            # cộng thêm công nợ cũ (có thể = 0 nếu chưa khai báo)
            record.residual_amount = (current_residual or 0.0) 
    @api.depends("contract_ids.amount")
    def _compute_total_contracts(self):
        for record in self:
            record.total_contracts = sum(record.contract_ids.mapped("amount"))
    @api.depends("contract_ids.total_settlements")
    def _compute_total_settlements(self):
        for record in self:
            record.total_settlements = sum(record.contract_ids.mapped("total_settlements"))
    @api.depends("total_invoices", "paid_amount")
    def _compute_advance_amount(self):
        for record in self:
            advance_amount = record.paid_amount - record.total_invoices
            if advance_amount < 0:
                advance_amount = 0
            record.advance_amount = advance_amount
            
    @api.depends("contract_ids.due_date")
    def _compute_due_date(self):
        today = date.today()

        for rec in self:
            # Lọc những contract có nợ > 0 và có due_date
            valid_contracts = rec.contract_ids.filtered(
                lambda c: c.residual_amount != 0 and c.due_date
            )
            if valid_contracts:
                nearest_due = min(valid_contracts.mapped("due_date"))
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
    @api.depends("partner_id")
    def _compute_contract_ids(self):
        for rec in self:
            rec.contract_ids = self.env["supplier.contract"].search([("partner_id", "=", rec.partner_id.id)])

    def _inverse_contract_ids(self):
        # cho phép chỉnh sửa trực tiếp
        for rec in self:
            for contract in rec.contract_ids:
                contract.partner_id = rec.partner_id
    @api.depends("partner_id", "currency_id")
    def _compute_note(self):
        Note = self.env["supplier.summary.note"]
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
        Note = self.env["supplier.summary.note"]
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
        Note = self.env["supplier.summary.note"]
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
        Note = self.env["supplier.summary.note"]
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

    # @api.depends("partner_id", "currency_id")
    # def _compute_old_debt(self):
    #     Note = self.env["supplier.summary.note"]
    #     for rec in self:
    #         if rec.partner_id and rec.currency_id:
    #             n = Note.search([
    #                 ("partner_id", "=", rec.partner_id.id),
    #                 ("currency_id", "=", rec.currency_id.id),
    #             ], limit=1)
    #             rec.old_debt = n.old_debt if n else 0.0
    #         else:
    #             rec.old_debt = 0.0

    # def _inverse_old_debt(self):
    #     Note = self.env["supplier.summary.note"]
    #     for rec in self:
    #         if not (rec.partner_id and rec.currency_id):
    #             continue
    #         n = Note.search([
    #             ("partner_id", "=", rec.partner_id.id),
    #             ("currency_id", "=", rec.currency_id.id),
    #         ], limit=1)
    #         if n:
    #             n.old_debt = rec.old_debt or 0.0
    #         else:
    #             Note.create({
    #                 "partner_id": rec.partner_id.id,
    #                 "currency_id": rec.currency_id.id,
    #                 "old_debt": rec.old_debt or 0.0,
    #             })

class ReportSupplierSummary(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_supplier_summary_view'
    _description = 'Supplier Summary Report'

    def _get_report_values(self, docids, data=None):
        # BỎ QUA docids, luôn lấy tất cả record
        docs = self.env['supplier.summary'].search([])
        return {
            'doc_ids': docs.ids,
            'doc_model': 'supplier.summary',
            'docs': docs,
        }

class SupplierSummaryNote(models.Model):
    _name = "supplier.summary.note"
    _description = "Ghi chú tổng hợp công nợ theo Nhà cung cấp"
    _rec_name = "partner_id"

    partner_id = fields.Many2one(
        "res.partner", string="Nhà cung cấp",
        required=True, domain=[("supplier_rank", ">", 0)], ondelete="cascade"
    )
    # NEW: tiền tệ gắn với ghi chú công nợ cũ
    currency_id = fields.Many2one(
        "res.currency", string="Tiền tệ", required=True,
        default=lambda self: self.env.company.currency_id
    )
    # NEW: công nợ cũ để người dùng nhập
    old_debt = fields.Monetary(
        string="Công nợ cũ",
        currency_field="currency_id",
        help="Số tiền còn nợ trước đây (sẽ cộng vào Còn nợ hiện tại)."
    )

    note = fields.Text("Ghi chú")
    interpretation = fields.Char("Diễn giải")

    _sql_constraints = [
        # đổi unique: mỗi (nhà cung cấp, tiền tệ) có đúng 1 bản ghi
        ("partner_currency_unique",
         "unique(partner_id, currency_id)",
         "Mỗi nhà cung cấp và tiền tệ chỉ có một ghi chú/công nợ cũ."),
    ]
