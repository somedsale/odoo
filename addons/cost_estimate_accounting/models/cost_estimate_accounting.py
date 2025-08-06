from odoo import models, fields, api
class CostEstimateAccounting(models.Model):
    _name = 'cost.estimate.accounting'
    _description = 'Bản dự toán cho kế toán'

    cost_estimate_id = fields.Many2one('cost.estimate', string="Phiếu dự toán", required=True)
    code = fields.Char(related='cost_estimate_id.code', string='Mã dự toán', store=True)
    name = fields.Char(related='cost_estimate_id.name', string='Tên dự toán', store=True)
    project_id = fields.Many2one(related='cost_estimate_id.project_id', string='Dự án', store=True)
    sale_order_id = fields.Many2one(related='cost_estimate_id.sale_order_id', string='Đơn hàng', store=True)
    total_cost = fields.Float(related='cost_estimate_id.total_cost', string='Tổng chi phí', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)


    line_ids = fields.One2many(
        related='cost_estimate_id.line_ids',
        string='Chi tiết dòng dự toán',
        readonly=True,
        store=False
    )

    @api.model
    def load_cost_estimate_data(self):
        estimates = self.env['cost.estimate'].search([('state', '=', 'approved')])
        for estimate in estimates:
            # Chỉ tạo nếu chưa tồn tại dòng tương ứng
            if not self.search([('cost_estimate_id', '=', estimate.id)]):
                self.create({
                    'cost_estimate_id': estimate.id,
                })
    @api.model
    def init(self):
        self.load_cost_estimate_data()

    
