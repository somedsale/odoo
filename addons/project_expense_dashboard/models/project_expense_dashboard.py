from odoo import models, fields, api

class ProjectExpenseDashboard(models.Model):
    _name = 'project.expense.dashboard'
    _description = 'Dashboard quản lý chi phí dự án'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        required=True,
        ondelete='cascade',
    )
    cost_estimate_id = fields.Many2one('cost.estimate', string="Dự toán", required=False)
    cost_estimate_line_ids = fields.One2many(
        related='cost_estimate_id.line_ids',
        string="Dòng dự toán",
        readonly=True,
    )
    total_estimate = fields.Float(string="Tổng dự toán", compute="_compute_total_estimate", store=True)
    total_actual = fields.Float(string="Tổng chi thực tế", compute="_compute_total_actual", store=True)
    progress = fields.Float(string="Tỷ lệ chi tiêu (%)", compute="_compute_progress", store=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", default=lambda self: self.env.company.currency_id, readonly=True)
    payment_request_count = fields.Integer(
    string="Số phiếu chi",
    compute="_compute_payment_request_count",
    store=False
)

    @api.depends('project_id')
    def _compute_payment_request_count(self):
        for record in self:
            record.payment_request_count = self.env['account.payment.request'].search_count([('project_id', '=', record.project_id.id)])


    @api.depends('cost_estimate_id')
    def _compute_total_estimate(self):
        for record in self:
            record.total_estimate = record.cost_estimate_id.total_cost if record.cost_estimate_id and hasattr(record.cost_estimate_id, 'total_cost') else 0.0

    @api.depends('project_id')
    def _compute_total_actual(self):
        for record in self:
            if record.project_id:
                total = self.env['account.payment.request'].search_read(
                    [('project_id', '=', record.project_id.id), ('state', '=', 'done')],
                    ['total']
                )
                record.total_actual = sum(line['total'] for line in total)
            else:
                record.total_actual = 0.0
            
    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.project_id:
            estimate = self.env['cost.estimate'].search([('project_id', '=', self.project_id.id)])
            if estimate:
                self.cost_estimate_id = estimate.id
            else:
                self.cost_estimate_id = False
        else:
            self.cost_estimate_id = False

    @api.depends('total_estimate', 'total_actual')
    def _compute_progress(self):
        for record in self:
            if record.total_estimate > 0:
                record.progress = (record.total_actual / record.total_estimate) * 100
            else:
                record.progress = 0.0

    def action_view_cost_estimate(self):
        """Hành động để xem chi tiết dự toán"""
        self.ensure_one()
        if self.cost_estimate_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'cost.estimate',
                'view_mode': 'form',
                'res_id': self.cost_estimate_id.id,
                'target': 'current',
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Không có dự toán',
                'message': 'Không tìm thấy dự toán cho dự án này.',
                'type': 'warning',
            }
        }
    def action_view_payment_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Phiếu chi của dự án',
            'res_model': 'account.payment.request',
            'view_mode': 'tree,form',
            'domain': [
                ('project_id', '=', self.project_id.id),
                ('state', '=', 'done')
            ],
            'context': {'default_project_id': self.project_id.id},
            'target': 'new',
        }