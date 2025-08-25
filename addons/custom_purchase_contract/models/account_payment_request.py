from odoo import fields, models, api
class AccountingPaymentRequest(models.Model):
    _inherit = 'account.payment.request'
    purchase_contract_id = fields.Many2one('purchase.contract', string="Hợp đồng mua", help="Hợp đồng mua liên quan đến yêu cầu chi tiền này")
    vendor_id = fields.Many2one('res.partner',related='purchase_contract_id.supplier_id', string="Nhà cung cấp", domain="[('supplier_rank', '>', 0)]")
    obj_type = fields.Selection([
        ('vendor', 'Nhà cung cấp'),
        ('employee', 'Nhân viên'),
        ('other', 'Khác')
    ], string="Cho chi", default='employee')

    @api.onchange('purchase_contract_id')
    def _onchange_purchase_contract_id(self):
        for rec in self:
            if rec.purchase_contract_id:
                # Tự động gán nhà cung cấp từ hợp đồng mua
                rec.vendor_id = rec.purchase_contract_id.supplier_id
                # Tự động gán dự án từ hợp đồng mua (nếu chưa có dự án từ proposal_sheet_id)
                if not rec.project_id:
                    rec.project_id = rec.purchase_contract_id.project_id
                # Tự động gán số tiền từ giá trị hợp đồng (nếu cần)
                rec.total = rec.purchase_contract_id.due_amount if rec.purchase_contract_id.due_amount else rec.total
                # Gán tiền tệ từ hợp đồng mua
                rec.currency_id = rec.purchase_contract_id.currency_id
    # def action_payment_request(self):
    #     res = super(AccountingPaymentRequest, self).action_payment_request()
    #     if self.obj_type == 'vendor' and self.purchase_contract_id:
    #         # Nếu là nhà cung cấp, liên kết với hợp đồng mua
    #         self.env['purchase.contract'].search([('id', '=', self.purchase_contract_id.id)]).write({
    #             'paid_amount': self.purchase_contract_id.due_amount - self.total,
    #         })
    #     return res