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
    ('submitted', 'Để Trình'),
    ('waiting_boss', 'Đã Trình'),
    ('approved', 'Đã Phê Duyệt'),
    ('done', 'Hoàn Tất'),
    ('rejected', 'Bị Từ Chối'),
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
    show_button_submit = fields.Boolean(compute='_compute_show_buttons')
    show_button_manager_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_boss_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_done = fields.Boolean(compute='_compute_show_buttons')
    show_button_reject = fields.Boolean(compute='_compute_show_buttons')
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
        if not vals.get('task_id') and self.env.context.get('default_task_id'):
            task = self.env['project.task'].browse(self.env.context.get('default_task_id'))
            vals['task_id'] = task.id
        if not vals.get('project_id'):
            vals['project_id'] = task.project_id.id
            
        if not vals.get('task_id'):
            raise ValidationError("Nhiệm vụ là bắt buộc.")
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('proposal.sheet') or 'PROP/00000'
        return super().create(vals)

    def write(self, vals):
        for rec in self:
            # Chỉ kiểm tra nếu trong vals có type VÀ nó khác type hiện tại
            if 'type' in vals and vals['type'] != rec.type:
                if rec.material_line_ids or rec.expense_line_ids:
                    raise ValidationError(
                        "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí."
                    )
        return super(ProposalSheet, self).write(vals)
    def unlink(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Không thể xóa khi phiếu không ở trạng thái Nháp.")
        return super().unlink()

    @api.constrains('material_line_ids', 'expense_line_ids', 'type')
    def _check_lines(self):
        if self.env.context.get('skip_check_lines'):
            return
        for rec in self:
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

    def action_submit(self):
        self.ensure_one()
    # Kiểm tra bắt buộc có dòng trước khi submit
        if self.type == 'material' and not self.material_line_ids:
            raise ValidationError("Phiếu đề xuất vật tư phải có ít nhất một dòng vật tư trước khi gửi duyệt.")
        if self.type == 'expense' and not self.expense_line_ids:
            raise ValidationError("Phiếu đề xuất chi phí phải có ít nhất một dòng chi phí trước khi gửi duyệt.")        
        if self.state != 'draft':
            raise UserError("Chỉ phiếu ở trạng thái nháp mới được gửi duyệt.")
        self.state = 'submitted'
        self.message_post(body="Phiếu đề xuất đã được gửi duyệt.")

    def action_manager_approve(self):
        if self.state != 'submitted':
            raise UserError("Chỉ phiếu đang Để Trình mới được duyệt.")
        if self.task_id.project_id.user_id != self.env.user:
            raise UserError("Bạn không phải là Quản lý dự án.")
        self.state = 'waiting_boss'
        self.message_post(body="Quản lý đã duyệt. Phiếu được chuyển lên Sếp.")

    def action_boss_approve(self):
        if self.state != 'waiting_boss':
            raise UserError("Chỉ phiếu đang Đã Trình mới được duyệt.")
        if self.approver_boss_id != self.env.user:
            raise UserError("Bạn không phải là Sếp.")
        self.state = 'approved'
        self.message_post(body="Sếp đã phê duyệt phiếu đề xuất.")

    def action_done(self):
        if self.state != 'approved':
            raise UserError("Chỉ phiếu đã phê duyệt mới được hoàn tất.")
        self.state = 'done'
        self.message_post(body="Phiếu đề xuất đã hoàn tất.")

    def action_reset_to_draft(self):
        if self.state != 'rejected':
            raise UserError("Chỉ phiếu bị từ chối mới được reset về nháp.")
        self.state = 'draft'
        self.message_post(body="Phiếu được reset về Nháp.")


    @api.depends('state', 'task_id.project_id.user_id', 'approver_boss_id')
    def _compute_show_buttons(self):
        for rec in self:
            is_team_lead = rec.task_id.project_id.user_id == self.env.user if rec.task_id.project_id else False
            is_boss = rec.approver_boss_id == self.env.user if rec.approver_boss_id else False

            rec.show_button_submit = rec.state == 'draft'
            rec.show_button_manager_approve = rec.state == 'submitted' and is_team_lead
            rec.show_button_boss_approve = rec.state == 'waiting_boss' and is_boss
            rec.show_button_done = rec.state == 'approved'
            rec.show_button_reject = rec.state in ['submitted', 'waiting_boss'] and (is_team_lead or is_boss)

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
    
    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id and not self.project_id:
            self.project_id = self.task_id.project_id.id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if not self.env.context.get('from_task'):
            self.task_id = False
        return {'domain': {'task_id': [('project_id', '=', self.project_id.id)]}}

    approver_boss_id = fields.Many2one(
        'res.users', string="Người Duyệt Cuối",
        default=lambda self: self.env['project.config'].get_default_boss() if self.env['project.config'].search([]) else False,
        readonly=True
    )
    # estimate_line_id = fields.Many2one('cost.estimate.line', string='Nguồn từ dự toán')
    def action_load_from_estimate(self):
        self.ensure_one()

        if not self.type:
            raise ValidationError("Vui lòng chọn Loại đề xuất trước khi tải dữ liệu.")

        # Xóa dữ liệu cũ trước khi load
        self.material_line_ids = [(5, 0, 0)]
        self.expense_line_ids = [(5, 0, 0)]

        material_lines = []
        expense_lines = []

        if self.type == 'material':
            if not self.task_id:
                raise ValidationError("Phiếu loại Vật tư bắt buộc phải chọn Nhiệm vụ.")

            # Lấy tất cả dòng dự toán của task cho vật tư
            estimate_lines = self.env['cost.estimate.line'].search([
                ('task_id', '=', self.task_id.id),
                ('product_id.detailed_type', 'in', ['consu', 'product'])
            ])
            if not estimate_lines:
                raise ValidationError("Không tìm thấy vật tư nào trong dự toán cho Nhiệm vụ này.")

            for line in estimate_lines:
                for material_line in line.material_line_ids:
                    material_lines.append((0, 0, {
                        'material_id': material_line.material_id.id,
                        'quantity': material_line.quantity,
                        'unit': material_line.unit.id,
                        'price_unit': material_line.price_unit or 0.0,
                        'description': f"Từ dự toán: {material_line.material_id.display_name}",
                    }))

            if not material_lines:
                raise ValidationError("Không tìm thấy chi tiết vật tư nào trong dự toán cho Nhiệm vụ này.")
            self.material_line_ids = material_lines

        elif self.type == 'expense':
    # Lấy tất cả chi phí (service) theo dự án
            estimate_lines = self.env['cost.estimate.line'].search([
                ('cost_estimate_id.project_id', '=', self.project_id.id),
                ('product_id.detailed_type', '=', 'service')
            ])
            if not estimate_lines:
                raise ValidationError("Không tìm thấy chi phí nào trong dự toán của Dự án này.")

            for line in estimate_lines:
                expense = self.env['project.expense'].search([('name', '=', line.product_id.display_name)], limit=1)
                if not expense:
                    expense = self.env['project.expense'].create({
                        'name': line.product_id.display_name,
                        'default_unit': line.product_id.uom_id.id,
                        'price_unit': line.price_subtotal or 0.0
                    })

                expense_lines.append((0, 0, {
                    'expense_id': expense.id,
                    'quantity': 1.0,
                    'unit': expense.default_unit.id,
                    'price_unit': line.price_subtotal or 0.0,
                    'description': f"Từ dự toán: {line.product_id.display_name}",
                }))

            self.expense_line_ids = expense_lines



