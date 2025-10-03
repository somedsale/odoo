from odoo import models, fields

class Project(models.Model):
    _inherit = 'project.project'

    customer_invoice_ids = fields.One2many(
        'customer.invoice',    # model hóa đơn
        'project_id',          # field Many2one trên invoice
        string="Hóa đơn liên quan"
    )
    customer_contract_ids = fields.One2many(
        'customer.contract',  # model hợp đồng
        'project_id',         # field Many2one trên hợp đồng    
        string="Hợp đồng liên quan"
    )