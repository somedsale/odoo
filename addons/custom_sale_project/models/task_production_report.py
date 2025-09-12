from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date
from markupsafe import Markup
class TaskProductionReport(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _name = 'task.production.report'
    _description = 'Task Daily Production Report'
    _order = 'report_date desc'
    note = fields.Text(string='Khó khăn - vướng mắc', tracking=True)
    propose = fields.Text(string='Đề xuất', tracking=True)
    uom_id = fields.Many2one('uom.uom', string='Đơn vị tính',related='task_id.uom_id', required=True)
    task_id = fields.Many2one(
        'project.task', 
        string='Task', 
        required=True, 
        ondelete='cascade'
    )

    report_date = fields.Date(
        string='Ngày báo cáo',
        default=fields.Date.today,
        required=True,
        readonly=True
    )

    quantity_done = fields.Float(
        string='Sản lượng đạt được trong ngày',
        required=True,
        attrs="{'readonly': [('quantity_done_readonly', '=', True)]}",
    )

    quantity_done_readonly = fields.Boolean(compute='_compute_quantity_done_readonly')

    _sql_constraints = [
        ('unique_task_date', 'unique(task_id, report_date)', 'Chỉ được tạo một báo cáo mỗi ngày cho mỗi nhiệm vụ.')
    ]

    # Tính toán readonly cho field quantity_done nếu không phải hôm nay
    @api.depends('report_date')
    def _compute_quantity_done_readonly(self):
        today = fields.Date.today()
        for rec in self:
            rec.quantity_done_readonly = rec.report_date != today

    # Không cho tạo báo cáo cho ngày khác hôm nay
    @api.model
    def create(self, vals):
        if 'report_date' in vals and str(vals['report_date']) != str(date.today()):
            raise ValidationError("Chỉ được tạo báo cáo cho ngày hôm nay.")
        rec = super().create(vals)
        rec._validate_quantity_limit()
        rec._notify_project_manager()
        return rec

    # Không cho chỉnh sửa nếu không phải hôm nay
    def write(self, vals):
        for rec in self:
            if rec.report_date != date.today():
                raise ValidationError("Không thể chỉnh sửa báo cáo sau ngày đã nhập.")
        res = super().write(vals)
        for rec in self:
            rec._validate_quantity_limit()
            rec._notify_project_manager()
        return res

    # Luôn chặn xoá
    def unlink(self):
        raise ValidationError("Không được xoá báo cáo sản lượng sau khi đã tạo.")

    # Kiểm tra tổng sản lượng không vượt quá task.quantity
    def _validate_quantity_limit(self):
        for rec in self:
            if not rec.task_id or not rec.task_id.quantity:
                continue

            total_done = sum(self.env['task.production.report'].search([
                ('task_id', '=', rec.task_id.id),
                ('id', '!=', rec.id)
            ]).mapped('quantity_done'))

            total = total_done + rec.quantity_done

            if total > rec.task_id.quantity:
                raise ValidationError(
                    f"Tổng sản lượng ({total}) vượt quá kế hoạch ({rec.task_id.quantity})."
                )
    def open_task_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Task',
            'view_mode': 'form',
            'res_model': 'project.task',
            'res_id': self.task_id.id,
            'target': 'current',
        }
    # Gửi thông báo Discuss đến Trưởng dự án
    def _notify_project_manager(self):
        for rec in self:
            user_id = self.env.user
            task = rec.task_id
            project = task.project_id
            manager = project.user_id

            if manager and manager.partner_id:
                task.message_subscribe(partner_ids=[manager.partner_id.id])
                message_body = Markup('<ul>' \
                '<li>Báo cáo sản lượng mới đã được tạo cho nhiệm vụ <strong>{}</strong> trong dự án <strong>{}</strong>.</li>' \
                '<li>Ngày báo cáo: <strong>{}</strong></li>' \
                '<li>Người báo cáo: <strong>{}</strong></li>' \
                '<li>Sản lượng đạt được: <strong>{}</strong> <strong>{}</strong></li>' \
                '</ul>'.format(
                    task.name, 
                    project.name, 
                    rec.report_date.strftime('%d-%m-%Y'), 
                    self.env.user.name,
                    rec.quantity_done ,
                    (rec.uom_id.name or '')
                ))
                task.message_post(
                    body=message_body,
                    partner_ids=[manager.partner_id.id],
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )
