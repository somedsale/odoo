from odoo import models, fields, api

class ProjectExpenseCustom(models.Model):
    _name = 'project.expense.custom'
    _description = 'Chi phí dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    project_id = fields.Many2one('project.project', string="Dự án", required=True, index=True)
    total_cost = fields.Float(string="Tổng chi phí", compute='_compute_costs', store=True)
    total_spent = fields.Float(string="Tổng đã chi", compute='_compute_costs', store=True)
    total_not_spent = fields.Float(string="Tổng chưa chi", compute='_compute_costs', store=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", default=lambda self: self.env.company.currency_id)
    payment_request_ids = fields.One2many(
        'account.payment.request',
        'project_id',
        string="Yêu cầu chi tiền",
        compute="_compute_payment_requests",
        store=False  # hoặc không khai báo store
    )
    
    @api.depends('project_id')
    def _compute_payment_requests(self):
        for record in self:
            if record.project_id:
                record.payment_request_ids = self.env['account.payment.request'].search([
                    ('project_id', '=', record.project_id.id)
                ])
            else:
                record.payment_request_ids = self.env['account.payment.request']
    @api.depends('project_id')
    def _compute_costs(self):
        for record in self:
            if not record.project_id:
                record.total_cost = 0.0
                record.total_spent = 0.0
                record.total_not_spent = 0.0
                continue

            payment_requests = self.env['account.payment.request'].search([
                ('project_id', '=', record.project_id.id)
            ])
            total_spent = 0.0
            total_not_spent = 0.0
            for pr in payment_requests:
                if pr.status_expense == 'paid':
                    total_spent += pr.total
                elif pr.status_expense == 'not yet':
                    total_not_spent += pr.total
            total_cost = total_spent + total_not_spent

            record.total_cost = total_cost
            record.total_spent = total_spent
            record.total_not_spent = total_not_spent


    @api.model
    def create_or_update_expense(self, project_id):
        expense = self.search([('project_id', '=', project_id)], limit=1)
        if not expense:
            self.create({
                'project_id': project_id,
            })
        else:
            expense._compute_costs()

    @api.model
    def _load_all_projects(self):
        projects = self.env['project.project'].search([])
        for project in projects:
            self.create_or_update_expense(project.id)

    @api.model
    def init(self):
        self._load_all_projects()

    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Yêu cầu chi tiền',
            'res_model': 'account.payment.request',
            'view_mode': 'tree,form',
            'domain': [('project_id', '=', self.project_id.id)],
            'context': {'default_project_id': self.project_id.id},
        }