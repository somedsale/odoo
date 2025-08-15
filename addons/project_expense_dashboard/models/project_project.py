from odoo import models, fields

class ProjectProject(models.Model):
    _inherit = 'project.project'

    account_payment_request_ids = fields.One2many(
        'account.payment.request',  # model đích
        'project_id',               # field Many2one bên payment request
        string='Phiếu chi'
    )
