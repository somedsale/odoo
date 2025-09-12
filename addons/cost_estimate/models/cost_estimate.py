from odoo import models, fields, api
from markupsafe import Markup
from odoo.exceptions import UserError
class CostEstimate(models.Model):
    _name = 'cost.estimate'
    _description = 'Dự toán chi phí Dự án'
    _order = "create_date desc"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    code = fields.Char('Mã dự toán', required=True, copy=False, readonly=True,
         help='Mã định danh duy nhất của dự toán chi phí',default='New')
    name = fields.Char('Tên dự toán', required=True, default='New')
    requested_by = fields.Many2one('res.users', string='Người tạo dự toán', default=lambda self: self.env.user, readonly=True)
    project_id = fields.Many2one('project.project', string='Dự án', ondelete='restrict')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', ondelete='restrict')
    line_ids = fields.One2many('cost.estimate.line', 'cost_estimate_id', string='Chi tiết dự toán')
    director_user_id = fields.Many2one('res.users', string="Giám Đốc", default=lambda self: self._default_director_user(), readonly=True)
    show_button_submit = fields.Boolean(compute='_compute_show_button')
    show_button_approve = fields.Boolean(compute='_compute_show_button')
    show_button_cancel = fields.Boolean(compute='_compute_show_button')
    show_button_draft = fields.Boolean(compute='_compute_show_button')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    total_cost = fields.Float(
        string='Tổng chi phí',
        compute='_compute_total_cost',
        store=True,
        digits=(16, 0)
    )
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Gủi duyệt'),
        ('approved', 'Đã phê duyệt'),
        ('rejected', 'Bị từ chối'),
        ('cancel', 'Hủy bỏ')
    ], string='Trạng thái', default='draft', required=True, copy=False)
    @api.depends('state')
    def _compute_show_button(self):
        for rec in self:
            is_creator = rec.requested_by == self.env.user
            is_director = rec.director_user_id == self.env.user
            rec.show_button_submit = rec.state == 'draft'
            rec.show_button_draft = rec.state == 'approved' and is_director
            rec.show_button_approve = rec.state == 'submitted' and is_director
            rec.show_button_cancel = rec.state in ['draft', 'submitted'] and is_creator

    @api.model
    def _default_director_user(self):
        group = self.env.ref('custom_director_role.group_director')  # đổi lại module ID cho đúng
        users = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1)
        return users.id if users else False
    def action_submit(self):
        for rec in self:
            rec.state = 'submitted'
            partner_ids = [rec.director_user_id.partner_id.id, rec.requested_by.partner_id.id]
            self.message_subscribe(partner_ids=partner_ids)
            self.message_post(
                body=Markup(
                    '<p>Dự toán chi phí <strong>{}</strong> đã được gửi duyệt.</p>'
                ).format(rec.name),
                subtype_xmlid='mail.mt_comment',
                message_type='comment'
            )
    def action_approve(self):
        for rec in self:
            rec.state = 'approved'
            self.env['project.expense.dashboard'].create({
                            'project_id': rec.project_id.id,
                            'cost_estimate_id':  rec.id,
            })   
            self.message_post(
                body=Markup(
                    '<p>Dự toán chi phí <strong>{}</strong> đã được phê duyệt.</p>'
                ).format(rec.name),
                subtype_xmlid='mail.mt_comment',
                message_type='comment'
            )
    def action_cancel(self):
        for rec in self:
            rec.state = 'cancel'
    def action_draft(self):
        for rec in self:
            rec.state = 'draft'
    @api.depends('line_ids.price_subtotal')
    def _compute_total_cost(self):
        for rec in self:
            rec.total_cost = sum(line.price_subtotal for line in rec.line_ids)
    @api.model
    def create(self, vals):
        if not vals.get('code'):
            vals['code'] = self.env['ir.sequence'].next_by_code('cost.estimate.code') or '/'
        return super().create(vals)