from odoo import fields, models, api
class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'
    # supplier_debt_summary_id = fields.Many2one('supplier.debt.summary', string="Tổng hợp công nợ nhà cung cấp", help="Tổng hợp công nợ liên quan đến yêu cầu chi tiền này")