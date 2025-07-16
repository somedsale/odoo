from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)

class ProposalSheet(models.Model):
    _name = 'proposal.sheet'
    _description = 'Phiếu Đề Xuất'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Mã Đề Xuất', default='New', readonly=True, copy=False)
    project_id = fields.Many2one('project.project', string='Dự án', required=True, tracking=True)
    task_id = fields.Many2one('project.task', string='Nhiệm Vụ', required=True, tracking=True)
    requested_by = fields.Many2one('res.users', string='Người Đề Xuất', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('submitted', 'Chờ Duyệt'),
        ('approved', 'Đã Duyệt'),
        ('done', 'Hoàn Tất'),
    ], default='draft', string='Trạng Thái', tracking=True)
    type = fields.Selection([
        ('material', 'Vật Tư'),
        ('expense', 'Chi Phí'),
    ], required=True, string='Loại Đề Xuất', tracking=True)
    material_line_ids = fields.One2many(
        'proposal.material.line', 'sheet_id',
        string='Chi Tiết Vật Tư',
        domain=[('type', '=', 'material')],
        copy=True
    )
    expense_line_ids = fields.One2many(
        'proposal.expense.line', 'sheet_id',
        string='Chi Tiết Chi Phí',
        domain=[('type', '=', 'expense')],
        copy=True
    )
    show_button_submit = fields.Boolean(compute='_compute_show_buttons', store=False)
    show_button_approve = fields.Boolean(compute='_compute_show_buttons', store=False)
    show_button_done = fields.Boolean(compute='_compute_show_buttons', store=False)
    is_type_readonly = fields.Boolean(compute='_compute_is_type_readonly', store=False)

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalSheet with vals: %s", vals)
        if not vals.get('type'):
            if vals.get('material_line_ids'):
                vals['type'] = 'material'
            elif vals.get('expense_line_ids'):
                vals['type'] = 'expense'
            else:
                raise ValidationError('Vui lòng chọn loại đề xuất trước khi lưu.')
        if not vals.get('task_id'):
            raise ValidationError("Nhiệm vụ là bắt buộc.")
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('proposal.sheet') or 'PROP/00000'
        return super().create(vals)

    def write(self, vals):
        _logger.info("Writing ProposalSheet with vals: %s", vals)
        if 'type' in vals and (self.material_line_ids or self.expense_line_ids):
            raise ValidationError(
                "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí."
            )
        return super().write(vals)

    @api.constrains('material_line_ids', 'expense_line_ids', 'type')
    def _check_lines(self):
        for rec in self:
            if rec.type == 'material' and not rec.material_line_ids:
                raise ValidationError("Phiếu đề xuất vật tư phải có ít nhất một dòng vật tư.")
            if rec.type == 'expense' and not rec.expense_line_ids:
                raise ValidationError("Phiếu đề xuất chi phí phải có ít nhất một dòng chi phí.")
            for line in rec.material_line_ids:
                if line.type != 'material':
                    raise ValidationError("Dòng vật tư có loại không hợp lệ.")
            for line in rec.expense_line_ids:
                if line.type != 'expense':
                    raise ValidationError("Dòng chi phí có loại không hợp lệ.")

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError("Chỉ phiếu ở trạng thái nháp mới được gửi duyệt.")
        self.state = 'submitted'
        self.message_post(body='Phiếu đề xuất đã được gửi duyệt.')

    def action_approve(self):
        self.ensure_one()
        if not self.task_id.project_id:
            raise UserError("Nhiệm vụ chưa được gán cho dự án.")
        if not self.task_id.project_id.user_id:
            raise UserError("Dự án chưa có trưởng nhóm được gán.")
        if self.task_id.project_id.user_id != self.env.user:
            raise UserError("Chỉ trưởng nhóm của dự án mới có quyền duyệt đề xuất.")
        if self.state != 'submitted':
            raise UserError("Chỉ phiếu ở trạng thái chờ duyệt mới được duyệt.")
        self.state = 'approved'
        self.message_post(body='Phiếu đề xuất đã được duyệt.')

    def action_done(self):
        self.ensure_one()
        if self.state != 'approved':
            raise UserError("Chỉ phiếu đã duyệt mới được hoàn tất.")
        self.state = 'done'
        self.message_post(body='Phiếu đề xuất đã hoàn tất.')

    @api.depends('state', 'task_id.project_id.user_id')
    def _compute_show_buttons(self):
        for rec in self:
            is_team_lead = rec.task_id.project_id.user_id == self.env.user if rec.task_id.project_id else False
            rec.show_button_submit = rec.state == 'draft'
            rec.show_button_approve = rec.state == 'submitted' and is_team_lead
            rec.show_button_done = rec.state == 'approved'

    @api.depends('material_line_ids', 'expense_line_ids')
    def _compute_is_type_readonly(self):
        for rec in self:
            rec.is_type_readonly = bool(rec.material_line_ids or rec.expense_line_ids)

    @api.onchange('type')
    def _onchange_type(self):
        if self.material_line_ids or self.expense_line_ids:
            raise ValidationError(
                "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí. "
                "Vui lòng xóa các dòng hiện có trước khi thay đổi."
            )

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'form' and self.type:
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//page"):
                page_string = node.get('string')
                if (self.type == 'material' and page_string != 'Chi Tiết Vật Tư') or \
                   (self.type == 'expense' and page_string != 'Chi Tiết Chi Phí'):
                    node.getparent().remove(node)
            res['arch'] = etree.tostring(doc, encoding='unicode')
        return res
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        task_id = self.env.context.get('default_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)
            res['task_id'] = task.id
            res['project_id'] = task.project_id.id
        return res
    
    is_task_locked = fields.Boolean(compute='_compute_lock_fields')
    is_project_locked = fields.Boolean(compute='_compute_lock_fields')

    @api.depends_context('from_task')
    def _compute_lock_fields(self):
        for rec in self:
            is_from_task = self.env.context.get('from_task')
            rec.is_task_locked = is_from_task
            rec.is_project_locked = is_from_task
    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id and not self.project_id:
            self.project_id = self.task_id.project_id.id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if not self.env.context.get('from_task'):
            self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    