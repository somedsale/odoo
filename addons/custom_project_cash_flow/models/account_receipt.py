from odoo import models, fields, api, _

class AccountReceipt(models.Model):
    _inherit = 'account.receipt'

    cash_flow_id = fields.Many2one(
        'project.cash.flow', 
        string='Dòng tiền dự án',
        readonly=True,
        copy=False
    )