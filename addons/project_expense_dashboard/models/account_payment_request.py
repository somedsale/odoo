from odoo import models, fields,api

class AccountPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    cost_estimate_line_id = fields.Many2one(
        'cost.estimate.line',
        string='Cost Estimate Line',
        ondelete='set null'
    )
    product_id = fields.Many2one(
        'product.template',
        string='Sản phẩm'
    )
    @api.onchange('project_id')
    def _onchange_project(self):
        if self.project_id:
            return {
                'domain': {
                    'cost_estimate_line_id': [('project_id', '=', self.project_id.id)]
                }
            }
