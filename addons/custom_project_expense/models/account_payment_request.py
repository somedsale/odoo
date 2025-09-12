from odoo import models, fields, api

class AccountPaymentRequest(models.Model):
    _inherit = 'account.payment.request'

    project_expense_id = fields.Many2one(
        'project.expense.custom', 
        string='Chi phí dự án', 
        compute='_compute_expense_id', 
        store=True,
        readonly=True
    )

    @api.depends('project_id')
    def _compute_expense_id(self):
        expense_model = self.env['project.expense.custom']
        for rec in self:
            project_expense = expense_model.search([('project_id', '=', rec.project_id.id)], limit=1)
            rec. project_expense_id = project_expense.id if project_expense else False
