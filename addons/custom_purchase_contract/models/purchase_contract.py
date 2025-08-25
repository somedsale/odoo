from odoo import fields, models, api

class PurchaseContract(models.Model):
    _name = 'purchase.contract'
    _description = 'Hợp đồng mua'

    name = fields.Char(string='Số hợp đồng', required=True)
    supplier_id = fields.Many2one('res.partner', string='Nhà cung cấp', required=True, domain=[('supplier_rank', '>', 0)])
    project_id = fields.Many2one('project.project', string='Dự án')
    date_signed = fields.Date(string='Ngày ký', default=fields.Date.today)
    date_start = fields.Date(string='Ngày bắt đầu')
    date_end = fields.Date(string='Ngày kết thúc')
    value = fields.Monetary(string='Giá trị hợp đồng', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    terms = fields.Text(string='Điều khoản')
    attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Tệp đính kèm', domain=[('res_model', '=', 'purchase.contract')])
    settlement_ids = fields.One2many('purchase.contract.settlement', 'purchase_contract_id', string='Hồ sơ quyết toán')
    paid_amount = fields.Monetary(string='Số tiền đã thanh toán', compute='_compute_paid_amount', store=True)
    account_payment_request_ids = fields.One2many('account.payment.request', 'purchase_contract_id', string='Phiếu chi')
    due_amount = fields.Monetary(string='Số tiền còn nợ', compute='_compute_due_amount', store=True)
    invoice_amount = fields.Monetary(string='Tổng giá trị hóa đơn', compute='_compute_due_amount', store=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('confirmed', 'Xác nhận'),
        ('done', 'Hoàn thành'),
        ('cancel', 'Hủy'),
    ], string='Trạng thái', default='draft')
    purchase_invoice_ids = fields.One2many('purchase.invoice', 'purchase_contract_id', string='Hóa đơn liên quan')
    # Nếu muốn liên kết với module công nợ trước, thêm:
    @api.depends('account_payment_request_ids.total','paid_amount')
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(request.total for request in record.account_payment_request_ids)
            record.due_amount = record.due_amount - record.paid_amount
    @api.depends('purchase_invoice_ids.amount_total','due_amount','paid_amount')
    def _compute_due_amount(self):
        for record in self:
            record.invoice_amount = sum(invoice.amount_total for invoice in record.purchase_invoice_ids)
            record.due_amount = record.invoice_amount - record.paid_amount
    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
# Model cho hồ sơ quyết toán
class PurchaseContractSettlement(models.Model):
    _name = 'purchase.contract.settlement'
    _description = 'Hồ sơ quyết toán hợp đồng'

    name = fields.Char(string='Số hồ sơ', required=True)
    amount = fields.Monetary(string='Số tiền', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    purchase_contract_id = fields.Many2one('purchase.contract', string='Hợp đồng')
    date_settlement = fields.Date(string='Ngày quyết toán', default=fields.Date.today)
    note = fields.Text(string='Ghi chú')
    # Tùy chọn: Thêm tệp đính kèm cho hồ sơ quyết toán
    # attachment_ids = fields.One2many('ir.attachment', 'res_id', string='Tệp đính kèm', domain=[('res_model', '=', 'purchase.contract.settlement')])
class PurchaseInvoice(models.Model):
    _name ="purchase.invoice"

    purchase_contract_id = fields.Many2one('purchase.contract', string='Hợp đồng mua', help='Hợp đồng liên quan đến hóa đơn này')
    name = fields.Char(string='Số hóa đơn', required=True)
    amount_total = fields.Monetary(string='Tổng tiền', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id)
    create_date = fields.Datetime(string='Ngày tạo', default=fields.Datetime.now)