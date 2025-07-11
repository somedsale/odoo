from odoo import models, fields, api
from odoo.exceptions import UserError

class MaterialRequest(models.Model):
    _name = 'material.request'
    _description = 'Đề xuất vật tư'

    name = fields.Char(string='Mã đề xuất', default='New', readonly=True)
    task_id = fields.Many2one('project.task', string='Nhiệm vụ', required=True)
    requested_by = fields.Many2one('res.users', string='Người đề xuất', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('done', 'Hoàn tất'),
    ], default='draft', string='Trạng thái')
    line_ids = fields.One2many('material.request.line', 'request_id', string='Chi tiết vật tư')

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('material.request') or '/'
        return super().create(vals)

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError('Chỉ được gửi khi ở trạng thái nháp')
            rec.state = 'submitted'

    def action_approve(self):
        for rec in self:
            is_creator = rec.requested_by == self.env.user
            is_team_lead = rec.task_id.project_user_id == self.env.user

            if is_creator and not is_team_lead:
                raise UserError("Bạn là người tạo đề xuất nhưng không phải trưởng nhóm nên không có quyền duyệt.")

            if not is_team_lead:
                raise UserError("Chỉ trưởng nhóm mới có quyền duyệt đề xuất này.")

            rec.state = 'approved'

    def action_done(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError('Chỉ hoàn tất khi đã được duyệt')
            rec.state = 'done'


    show_button_submit = fields.Boolean(compute='_compute_show_button_submit', store=False)
    show_button_approve = fields.Boolean(compute='_compute_show_button_approve', store=False)
    show_button_done = fields.Boolean(compute='_compute_show_button_done', store=False)

    def _compute_show_button_submit(self):
        for rec in self:
            rec.show_button_submit = rec.state == 'draft'

    def _compute_show_button_approve(self):
        for rec in self:
            is_team_lead = rec.task_id.project_user_id == self.env.user
            rec.show_button_approve = rec.state == 'submitted' and is_team_lead

    def _compute_show_button_done(self):
        for rec in self:
            rec.show_button_done = rec.state == 'approved'
    
    