from odoo import models, fields, api, tools
from datetime import date

class SupplierSummary(models.Model):
    _name = "supplier.summary"
    _description = "Tổng hợp công nợ nhà cung cấp"
    _auto = False
    partner_id = fields.Many2one("res.partner", string="Nhà cung cấp", domain=[("supplier_rank", ">", 0)])
    contract_ids = fields.One2many(
        "supplier.contract",
        compute="_compute_contract_ids",
        inverse="_inverse_contract_ids",
        string="Hợp đồng"
    )
    interpretation = fields.Char("Diễn giải", compute="_compute_interpretation")
    due_date = fields.Date("Ngày đến hạn" , compute="_compute_due_date")
    due_days = fields.Char("Số ngày đến hạn", compute="_compute_due_date")
    total_contracts = fields.Monetary("Tổng giá trị hợp đồng", compute="_compute_total_contracts")
    total_invoices = fields.Monetary("Tổng giá trị hóa đơn", compute="_compute_total_invoices", currency_field="currency_id")
    paid_amount = fields.Monetary("Tổng giá trị đã thanh toán", compute="_compute_paid_amount", currency_field="currency_id")
    residual_amount = fields.Monetary("Còn nợ", compute="_compute_residual", currency_field="currency_id")
    advance_amount = fields.Monetary("Số tiền đã tạm ứng/ chưa hóa đơn", compute="_compute_advance_amount", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ")
    
    def init(self):
        """Create or update the database view for supplier.summary."""
        tools.drop_view_if_exists(self.env.cr, self._table)  # Drop the view if it exists
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW supplier_summary AS (
                SELECT
                    row_number() OVER () AS id,  -- Generate a unique ID for the view
                    sc.partner_id AS partner_id,
                    sc.currency_id AS currency_id,
                    SUM(sc.amount) AS total_contracts,
                    SUM(sc.total_invoices) AS total_invoices,
                    SUM(sc.paid_amount) AS paid_amount,
                    SUM(sc.residual_amount) AS residual_amount
                FROM supplier_contract sc
                LEFT JOIN res_partner rp ON sc.partner_id = rp.id
                LEFT JOIN res_currency rc ON sc.currency_id = rc.id
                GROUP BY sc.partner_id, sc.currency_id
            )
        """)
    @api.depends("contract_ids.total_invoices")
    def _compute_total_invoices(self):
        for record in self:
            record.total_invoices = sum(record.contract_ids.mapped("total_invoices"))
    @api.depends("contract_ids.paid_amount")
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(record.contract_ids.mapped("paid_amount"))
    @api.depends("contract_ids.residual_amount")
    def _compute_residual(self):
        for record in self:
            residual_amount = sum(record.contract_ids.mapped("residual_amount"))
            if residual_amount < 0:
                residual_amount = 0
            record.residual_amount = residual_amount
    @api.depends("contract_ids.amount")
    def _compute_total_contracts(self):
        for record in self:
            record.total_contracts = sum(record.contract_ids.mapped("amount"))
    @api.depends("total_invoices", "paid_amount")
    def _compute_advance_amount(self):
        for record in self:
            advance_amount = record.paid_amount - record.total_invoices
            if advance_amount < 0:
                advance_amount = 0
            record.advance_amount = advance_amount
    @api.depends("contract_ids.create_date", "contract_ids.interpretation")
    def _compute_interpretation(self):
        for rec in self:
            if rec.contract_ids:
                # Sắp xếp theo create_date giảm dần (lấy hợp đồng mới nhất)
                latest_contract = rec.contract_ids.sorted(lambda c: c.create_date or fields.Datetime.now(), reverse=True)[0]
                rec.interpretation = latest_contract.interpretation
            else:
                rec.interpretation = False
            
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
                    rec.due_days = f"Còn {delta} ngày - {nearest_due.strftime('%d/%m/%Y')}"
                elif delta == 0:
                    rec.due_days = f"Đến hạn hôm nay - {nearest_due.strftime('%d/%m/%Y')}"
                else:
                    rec.due_days = f"Quá hạn {abs(delta)} ngày - {nearest_due.strftime('%d/%m/%Y')}"
            else:
                rec.due_date = False
                rec.due_days = "-"
    def _compute_contract_ids(self):
        for rec in self:
            rec.contract_ids = self.env["supplier.contract"].search([("partner_id", "=", rec.partner_id.id)])

    def _inverse_contract_ids(self):
        # cho phép chỉnh sửa trực tiếp
        for rec in self:
            for contract in rec.contract_ids:
                contract.partner_id = rec.partner_id
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
