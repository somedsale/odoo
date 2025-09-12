from odoo import models, fields

class ProjectPaymentMilestone(models.Model):
    _name = 'project.payment.milestone'
    _description = 'Mốc thanh toán dự án'
    _order = 'name asc'

    name = fields.Char('Tên mốc thanh toán', required=True)
    note = fields.Text('Ghi chú')
