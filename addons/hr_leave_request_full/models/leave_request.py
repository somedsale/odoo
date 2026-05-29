# -*- coding: utf-8 -*-
from datetime import timedelta

from markupsafe import Markup, escape
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SomedLeaveRequestLine(models.Model):
    _name = 'somed.leave.request.line'
    _description = 'Chi tiết mốc nghỉ phép'
    _order = 'date_from, id'

    request_id = fields.Many2one('somed.leave.request', string='Đơn nghỉ phép', required=True, ondelete='cascade')
    leave_type = fields.Char(string='Nội dung', default='Nghỉ phép', required=True)
    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    total_days = fields.Float(string='Tổng ngày nghỉ', compute='_compute_total_days', store=True)
    note = fields.Char(string='Ghi chú')

    @api.depends('date_from', 'date_to')
    def _compute_total_days(self):
        for line in self:
            if line.date_from and line.date_to:
                delta = (line.date_to - line.date_from).days + 1
                line.total_days = max(delta, 0)
            else:
                line.total_days = 0.0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_to < line.date_from:
                raise ValidationError(_('Đến ngày không được nhỏ hơn Từ ngày.'))


class SomedLeaveRequest(models.Model):
    _name = 'somed.leave.request'
    _description = 'Đơn xin nghỉ phép'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Mã đơn', default='/', readonly=True, copy=False, tracking=True)
    request_date = fields.Date(string='Ngày làm đơn', default=fields.Date.context_today, required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Nhân viên', default=lambda self: self.env.user.employee_id, required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Người làm đơn', related='employee_id.user_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', string='Vị trí', related='employee_id.job_id', store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Trưởng bộ phận', compute='_compute_manager', store=True)
    manager_user_id = fields.Many2one('res.users', string='User trưởng bộ phận', compute='_compute_manager', store=True)

    line_ids = fields.One2many('somed.leave.request.line', 'request_id', string='Các mốc thời gian nghỉ', copy=True)
    date_from = fields.Date(string='Từ ngày', compute='_compute_summary', store=True)
    date_to = fields.Date(string='Đến ngày', compute='_compute_summary', store=True)
    total_days = fields.Float(string='Tổng ngày nghỉ', compute='_compute_summary', store=True)

    reason = fields.Text(string='Lý do', required=True)
    note = fields.Text(string='Ghi chú')
    handover_employee_id = fields.Many2one('hr.employee', string='Người phụ trách công việc')
    handover_phone = fields.Char(string='Số điện thoại người phụ trách')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('manager_waiting', 'Chờ trưởng bộ phận'),
        ('hr_waiting', 'Chờ quản trị viên HR'),
        ('director_waiting', 'Chờ giám đốc'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True, copy=False)

    manager_approved_by = fields.Many2one('res.users', string='Trưởng bộ phận duyệt', readonly=True, copy=False)
    manager_approved_date = fields.Date(string='Ngày trưởng bộ phận duyệt', readonly=True, copy=False)
    hr_approved_by = fields.Many2one('res.users', string='Quản trị viên HR duyệt', readonly=True, copy=False)
    hr_approved_date = fields.Date(string='Ngày HR duyệt', readonly=True, copy=False)
    director_approved_by = fields.Many2one('res.users', string='Giám đốc duyệt', readonly=True, copy=False)
    director_approved_date = fields.Date(string='Ngày giám đốc duyệt', readonly=True, copy=False)
    reject_reason = fields.Text(string='Lý do từ chối', readonly=True, copy=False)

    can_submit = fields.Boolean(compute='_compute_button_visibility')
    can_manager_approve = fields.Boolean(compute='_compute_button_visibility')
    can_hr_approve = fields.Boolean(compute='_compute_button_visibility')
    can_director_approve = fields.Boolean(compute='_compute_button_visibility')
    can_reject = fields.Boolean(compute='_compute_button_visibility')
    can_cancel = fields.Boolean(compute='_compute_button_visibility')
    can_reset = fields.Boolean(compute='_compute_button_visibility')

    @api.depends('employee_id.department_id.manager_id', 'employee_id.department_id.manager_id.user_id')
    def _compute_manager(self):
        for rec in self:
            manager = rec.employee_id.department_id.manager_id if rec.employee_id and rec.employee_id.department_id else False
            rec.manager_id = manager
            rec.manager_user_id = manager.user_id if manager else False

    @api.depends('line_ids.date_from', 'line_ids.date_to', 'line_ids.total_days')
    def _compute_summary(self):
        for rec in self:
            dates_from = rec.line_ids.mapped('date_from')
            dates_to = rec.line_ids.mapped('date_to')
            rec.date_from = min(dates_from) if dates_from else False
            rec.date_to = max(dates_to) if dates_to else False
            rec.total_days = sum(rec.line_ids.mapped('total_days'))

    def _get_director_group(self):
        return self.env.ref('custom_director_role.group_director', raise_if_not_found=False)

    def _get_director_users(self):
        group = self._get_director_group()
        return group.users if group else self.env['res.users']

    def _is_director(self):
        group = self._get_director_group()
        return bool(group and group in self.env.user.groups_id)

    def _is_hr_manager(self):
        return self.env.user.has_group('hr.group_hr_manager')

    def _get_hr_manager_users(self):
        group = self.env.ref('hr.group_hr_manager', raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    @api.depends('state', 'employee_id', 'manager_user_id')
    def _compute_button_visibility(self):
        current = self.env.user
        is_hr = self._is_hr_manager()
        is_director = self._is_director()
        for rec in self:
            is_creator = bool(rec.employee_id.user_id and rec.employee_id.user_id == current)
            is_manager = bool(rec.manager_user_id and rec.manager_user_id == current)
            rec.can_submit = rec.state == 'draft' and is_creator
            rec.can_manager_approve = rec.state == 'manager_waiting' and is_manager
            rec.can_hr_approve = rec.state == 'hr_waiting' and is_hr
            rec.can_director_approve = rec.state == 'director_waiting' and is_director
            rec.can_reject = (
                (rec.state == 'manager_waiting' and is_manager)
                or (rec.state == 'hr_waiting' and is_hr)
                or (rec.state == 'director_waiting' and is_director)
            )
            rec.can_cancel = rec.state in ('draft', 'manager_waiting', 'hr_waiting', 'director_waiting') and is_creator
            rec.can_reset = rec.state == 'rejected' and is_creator

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('somed.leave.request') or '/'
        return super().create(vals_list)

    def _html_msg(self, title, message=''):
        return Markup('<p><strong>%s</strong></p><p>%s</p>') % (escape(title or ''), escape(message or ''))

    def _partner_ids_from_users(self, users):
        return users.filtered(lambda u: u.partner_id).mapped('partner_id').ids

    def _notify(self, title, message='', users=None, include_applicant=True):
        self.ensure_one()
        partner_ids = []
        if include_applicant and self.employee_id.user_id and self.employee_id.user_id.partner_id:
            partner_ids.append(self.employee_id.user_id.partner_id.id)
        if users:
            for pid in self._partner_ids_from_users(users):
                if pid not in partner_ids:
                    partner_ids.append(pid)
        if partner_ids:
            self.message_subscribe(partner_ids=partner_ids)
        self.message_post(
            body=self._html_msg(title, message),
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
            partner_ids=partner_ids,
        )

    def _close_all_activities(self, feedback='Đã xử lý'):
        for rec in self:
            activities = self.env['mail.activity'].search([
                ('res_model', '=', rec._name),
                ('res_id', '=', rec.id),
            ])
            if activities:
                activities.action_feedback(feedback=feedback)

    def _schedule_activities(self, users, summary, note):
        todo = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo:
            return
        for rec in self:
            for user in users:
                if user and user.active:
                    rec.activity_schedule(
                        activity_type_id=todo.id,
                        user_id=user.id,
                        summary=summary,
                        note=note,
                        date_deadline=fields.Date.today() + timedelta(days=3),
                    )

    def _check_lines_before_submit(self):
        self.ensure_one()
        if not self.line_ids:
            raise ValidationError(_('Vui lòng nhập ít nhất một mốc thời gian nghỉ.'))
        if self.total_days <= 0:
            raise ValidationError(_('Tổng ngày nghỉ phải lớn hơn 0.'))
        if not self.employee_id.user_id:
            raise ValidationError(_('Nhân viên chưa được gắn User đăng nhập.'))

    def action_submit(self):
        for rec in self:
            rec._check_lines_before_submit()
            if rec.state != 'draft':
                raise UserError(_('Chỉ đơn nháp mới được trình duyệt.'))
            rec._close_all_activities('Gửi duyệt mới')

            # Nếu người làm đơn là trưởng bộ phận của chính mình thì tự xác nhận bước trưởng bộ phận.
            if rec.manager_user_id and rec.manager_user_id == rec.employee_id.user_id:
                rec.write({
                    'state': 'hr_waiting',
                    'manager_approved_by': rec.manager_user_id.id,
                    'manager_approved_date': fields.Date.today(),
                })
                hr_users = rec._get_hr_manager_users()
                rec._notify(_('Đơn nghỉ phép đã tự xác nhận cấp trưởng bộ phận'), _('Đơn đang chờ Quản trị viên HR duyệt.'), users=hr_users)
                rec._schedule_activities(hr_users, _('Duyệt đơn nghỉ phép %s') % rec.name, _('Đơn nghỉ phép đang chờ Quản trị viên HR duyệt.'))
                continue

            if not rec.manager_user_id:
                raise ValidationError(_('Phòng ban của nhân viên chưa có Trưởng bộ phận hoặc Trưởng bộ phận chưa gắn User.'))

            rec.state = 'manager_waiting'
            rec._notify(_('Đơn nghỉ phép đã được gửi duyệt'), _('Đơn đang chờ Trưởng bộ phận duyệt.'), users=rec.manager_user_id)
            rec._schedule_activities(rec.manager_user_id, _('Duyệt đơn nghỉ phép %s') % rec.name, _('Đơn nghỉ phép đang chờ Trưởng bộ phận duyệt.'))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_manager_approve(self):
        for rec in self:
            if rec.state != 'manager_waiting' or rec.manager_user_id != self.env.user:
                raise UserError(_('Bạn không có quyền duyệt bước Trưởng bộ phận.'))
            rec._close_all_activities('Trưởng bộ phận đã duyệt')
            rec.write({
                'state': 'hr_waiting',
                'manager_approved_by': self.env.user.id,
                'manager_approved_date': fields.Date.today(),
            })
            hr_users = rec._get_hr_manager_users()
            rec._notify(_('Trưởng bộ phận đã duyệt đơn nghỉ phép'), _('Đơn đang chờ Quản trị viên HR duyệt.'), users=hr_users)
            rec._schedule_activities(hr_users, _('Duyệt đơn nghỉ phép %s') % rec.name, _('Đơn nghỉ phép đang chờ Quản trị viên HR duyệt.'))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_hr_approve(self):
        for rec in self:
            if rec.state != 'hr_waiting' or not rec._is_hr_manager():
                raise UserError(_('Bạn không có quyền duyệt bước Quản trị viên HR.'))
            rec._close_all_activities('Quản trị viên HR đã duyệt')
            rec.write({
                'state': 'director_waiting',
                'hr_approved_by': self.env.user.id,
                'hr_approved_date': fields.Date.today(),
            })
            director_users = rec._get_director_users()
            rec._notify(_('Quản trị viên HR đã duyệt đơn nghỉ phép'), _('Đơn đang chờ Giám đốc duyệt.'), users=director_users)
            rec._schedule_activities(director_users, _('Duyệt đơn nghỉ phép %s') % rec.name, _('Đơn nghỉ phép đang chờ Giám đốc duyệt.'))
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_director_approve(self):
        for rec in self:
            if rec.state != 'director_waiting' or not rec._is_director():
                raise UserError(_('Bạn không có quyền duyệt bước Giám đốc.'))
            rec._close_all_activities('Giám đốc đã duyệt')
            rec.write({
                'state': 'approved',
                'director_approved_by': self.env.user.id,
                'director_approved_date': fields.Date.today(),
            })
            users = self.env['res.users']
            if rec.handover_employee_id and rec.handover_employee_id.user_id:
                users |= rec.handover_employee_id.user_id
            rec._notify(_('Đơn nghỉ phép đã được Giám đốc duyệt'), _('Đơn đã hoàn tất phê duyệt.'), users=users)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_open_reject_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Từ chối đơn nghỉ phép'),
            'res_model': 'somed.leave.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_request_id': self.id},
        }

    def action_reject_with_reason(self, reason):
        for rec in self:
            rec._close_all_activities('Đơn đã bị từ chối')
            rec.write({
                'state': 'rejected',
                'reject_reason': reason,
            })
            rec._notify(_('Đơn nghỉ phép đã bị từ chối'), reason or '', users=False)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_cancel(self):
        for rec in self:
            if rec.state not in ('draft', 'manager_waiting', 'hr_waiting', 'director_waiting'):
                raise UserError(_('Không thể hủy đơn ở trạng thái hiện tại.'))
            rec._close_all_activities('Đơn đã bị hủy')
            rec.state = 'cancelled'
            rec._notify(_('Đơn nghỉ phép đã bị hủy'), _('Người làm đơn đã hủy đơn.'), users=False)
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_reset_to_draft(self):
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_('Chỉ đơn bị từ chối mới được đưa về nháp.'))
            rec._close_all_activities('Đưa về nháp')
            rec.write({
                'state': 'draft',
                'reject_reason': False,
                'manager_approved_by': False,
                'manager_approved_date': False,
                'hr_approved_by': False,
                'hr_approved_date': False,
                'director_approved_by': False,
                'director_approved_date': False,
            })
            rec._notify(_('Đơn nghỉ phép đã được đưa về nháp'), _('Bạn có thể chỉnh sửa và gửi lại.'), users=False)
        return {'type': 'ir.actions.client', 'tag': 'reload'}
