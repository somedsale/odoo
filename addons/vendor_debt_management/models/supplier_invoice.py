from odoo import models, fields,api
from odoo.exceptions import ValidationError

class SupplierInvoice(models.Model):
    _name = "supplier.invoice"
    _description = "Supplier Invoice"

    name = fields.Char("Số hóa đơn", required=True)
    contract_id = fields.Many2one("supplier.contract", string="Hợp đồng", required=True)
    settlement_id = fields.Many2one("supplier.settlement", string="Hồ sơ quyết toán")
    date = fields.Date("Ngày hóa đơn", required=True)
    amount = fields.Monetary("Số tiền", required=True, currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    partner_id = fields.Many2one(related="contract_id.partner_id", string="Nhà cung cấp", store=True)
    # project_id = fields.Many2one(related="contract_id.project_id", string="Dự án", store=True)
    due_date = fields.Date("Ngày đến hạn")
    note = fields.Text("Diễn giải")
    account_payment_request_ids = fields.One2many("account.payment.request", "invoice_id", string="Phiếu chi")
    purchase_id = fields.Many2one('purchase.order', string="Đơn mua hàng", index=True)
    project_id = fields.Many2one(
    "project.project",
    string="Dự án",
    store=True
)
    @api.onchange("contract_id")
    def _onchange_contract_id(self):
        for rec in self:
            if rec.contract_id:
                rec.project_id = rec.contract_id.project_id.id
    @api.constrains("date", "due_date")
    def _check_due_date(self):
        for record in self:
            if record.date and record.due_date and record.due_date < record.date:
                raise ValidationError("Ngày đến hạn không được nhỏ hơn Ngày hóa đơn.")
    _sql_constraints = [
        ("unique_invoice_name", "unique(name)", "Số hóa đơn đã tồn tại, vui lòng nhập số khác."),
    ]
class ReportSupplierInvoice(models.AbstractModel):
    _name = 'report.vendor_debt_management.report_supplier_invoice_view'
    _description = 'Supplier Invoice Report'
    def _get_report_values(self, docids, data=None):
        domain = []
        if data:
            date_from = data.get('date_from')
            date_to = data.get('date_to')
            if date_from and date_to:
                domain = [
                    ('date', '>=', date_from),
                    ('date', '<=', date_to),
                ]

        docs = self.env['supplier.invoice'].search(domain, order="date asc")

        return {
            'doc_ids': docs.ids,
            'doc_model': 'supplier.invoice',
            'docs': docs,
            'date_from': data.get('date_from'),
            'date_to': data.get('date_to'),
            'filter_type': data.get('filter_type'),
            'year': data.get('year'),
            'month': data.get('month'),
            'quarter': data.get('quarter'),
        }