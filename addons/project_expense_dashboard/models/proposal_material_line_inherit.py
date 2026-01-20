from odoo import models, fields

class ProposalMaterialLine(models.Model):
    _inherit = 'proposal.material.line'

    other_estimate_item = fields.Many2one(
        'estimate.item.other',
        string='Hạng mục khác',
    )
