# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup, escape


class SomedLeaveRequest(models.Model):
    _name = 'somed.leave.request'
    _description = 'Đơn xin nghỉ phép'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(string='Số đơn', default='New', copy=False, readonly=True, tracking=True)
    request_date = fields.Date(string='Ngày làm đơn', default=fields.Date.context_today, required=True, tracking=True)

    employee_id = fields.Many2one('hr.employee', string='Nhân viên', required=True, tracking=True,
                                  default=lambda self: self._default_employee_id())
    user_id = fields.Many2one('res.users', string='Người dùng tạo đơn', related='employee_id.user_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Phòng ban', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', string='Vị trí', related='employee_id.job_id', store=True, readonly=True)
    manager_id = fields.Many2one('hr.employee', string='Trưởng bộ phận', compute='_compute_manager', store=True, readonly=True)
    manager_user_id = fields.Many2one('res.users', string='User trưởng bộ phận', compute='_compute_manager', store=True, readonly=True)

    # Giữ các field tổng hợp này để hiển thị danh sách, tìm kiếm, report và tương thích dữ liệu cũ.
    # Dữ liệu chính của ngày nghỉ nằm ở line_ids để hỗ trợ nhiều mốc thời gian nghỉ.
    leave_type = fields.Selection([
        ('annual', 'Nghỉ phép'),
        ('sick', 'Nghỉ bệnh'),
        ('unpaid', 'Nghỉ không lương'),
        ('other', 'Khác'),
    ], string='Nội dung mặc định', default='annual', tracking=True)
    line_ids = fields.One2many('somed.leave.request.line', 'request_id', string='Các mốc thời gian nghỉ', copy=True)
    date_from = fields.Date(string='Từ ngày', compute='_compute_leave_summary', store=True, readonly=True)
    date_to = fields.Date(string='Đến ngày', compute='_compute_leave_summary', store=True, readonly=True)
    total_days = fields.Float(string='Tổng ngày nghỉ', compute='_compute_leave_summary', store=True)
    note = fields.Char(string='Ghi chú chung')
    reason = fields.Text(string='Lý do', required=True, tracking=True)

    handover_employee_id = fields.Many2one('hr.employee', string='Người phụ trách công việc')
    handover_phone = fields.Char(string='Số điện thoại người phụ trách')

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('manager_waiting', 'Chờ trưởng bộ phận duyệt'),
        ('hr_waiting', 'Chờ Quản trị viên HR duyệt'),
        ('director_waiting', 'Chờ giám đốc duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    manager_approved_by = fields.Many2one('res.users', string='Trưởng bộ phận đã duyệt', readonly=True, copy=False)
    manager_approved_date = fields.Date(string='Ngày trưởng bộ phận duyệt', readonly=True, copy=False)
    hr_approved_by = fields.Many2one('res.users', string='Quản trị viên HR đã duyệt', readonly=True, copy=False)
    hr_approved_date = fields.Date(string='Ngày HR duyệt', readonly=True, copy=False)
    director_approved_by = fields.Many2one('res.users', string='Giám đốc đã duyệt', readonly=True, copy=False)
    director_approved_date = fields.Date(string='Ngày giám đốc duyệt', readonly=True, copy=False)
    reject_reason = fields.Text(string='Lý do từ chối', readonly=True, copy=False, tracking=True)

    can_submit = fields.Boolean(compute='_compute_button_visibility')
    can_manager_approve = fields.Boolean(compute='_compute_button_visibility')
    can_hr_approve = fields.Boolean(compute='_compute_button_visibility')
    can_director_approve = fields.Boolean(compute='_compute_button_visibility')
    can_reject = fields.Boolean(compute='_compute_button_visibility')
    can_cancel = fields.Boolean(compute='_compute_button_visibility')
    can_reset = fields.Boolean(compute='_compute_button_visibility')

    @api.model
    def _default_employee_id(self):
        return self.env.user.employee_id.id or False

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = seq.next_by_code('somed.leave.request') or 'New'
        return super().create(vals_list)

    @api.depends('employee_id', 'employee_id.department_id', 'employee_id.department_id.manager_id', 'employee_id.department_id.manager_id.user_id')
    def _compute_manager(self):
        for rec in self:
            manager = rec.employee_id.department_id.manager_id if rec.employee_id and rec.employee_id.department_id else False
            rec.manager_id = manager
            rec.manager_user_id = manager.user_id if manager else False

    @api.depends('line_ids.date_from', 'line_ids.date_to', 'line_ids.total_days')
    def _compute_leave_summary(self):
        for rec in self:
            valid_lines = rec.line_ids.filtered(lambda l: l.date_from and l.date_to)
            if valid_lines:
                rec.date_from = min(valid_lines.mapped('date_from'))
                rec.date_to = max(valid_lines.mapped('date_to'))
                rec.total_days = sum(valid_lines.mapped('total_days'))
            else:
                rec.date_from = False
                rec.date_to = False
                rec.total_days = 0

    def _check_has_leave_lines(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Vui lòng nhập ít nhất một mốc thời gian nghỉ.'))
            invalid_lines = rec.line_ids.filtered(lambda l: not l.date_from or not l.date_to)
            if invalid_lines:
                raise UserError(_('Vui lòng nhập đầy đủ Từ ngày và Đến ngày cho tất cả mốc thời gian nghỉ.'))

    def _get_director_group(self):
        return self.env.ref('custom_director_role.group_director', raise_if_not_found=False)

    def _is_director(self, user=None):
        user = user or self.env.user
        group = self._get_director_group()
        return bool(group and group in user.groups_id)

    def _get_director_users(self):
        group = self._get_director_group()
        if not group:
            return self.env['res.users']
        return group.users.filtered(lambda u: u.active and u.partner_id)

    def _get_hr_admin_group(self):
        return self.env.ref('hr.group_hr_manager', raise_if_not_found=False)

    def _is_hr_admin(self, user=None):
        user = user or self.env.user
        group = self._get_hr_admin_group()
        return bool(group and group in user.groups_id)

    def _get_hr_admin_users(self):
        group = self._get_hr_admin_group()
        if not group:
            return self.env['res.users']
        return group.users.filtered(lambda u: u.active and u.partner_id)

    def _is_owner(self):
        self.ensure_one()
        return bool(self.employee_id.user_id and self.employee_id.user_id == self.env.user)

    @api.depends('state', 'employee_id.user_id', 'manager_user_id')
    def _compute_button_visibility(self):
        user = self.env.user
        for rec in self:
            is_owner = bool(rec.employee_id.user_id and rec.employee_id.user_id == user)
            is_manager = bool(rec.manager_user_id and rec.manager_user_id == user)
            is_hr = rec._is_hr_admin(user)
            is_director = rec._is_director(user)
            rec.can_submit = rec.state == 'draft' and is_owner
            rec.can_manager_approve = rec.state == 'manager_waiting' and is_manager
            rec.can_hr_approve = rec.state == 'hr_waiting' and is_hr
            rec.can_director_approve = rec.state == 'director_waiting' and is_director
            rec.can_reject = (
                (rec.state == 'manager_waiting' and is_manager)
                or (rec.state == 'hr_waiting' and is_hr)
                or (rec.state == 'director_waiting' and is_director)
            )
            rec.can_cancel = rec.state in ('draft', 'manager_waiting', 'hr_waiting', 'director_waiting') and is_owner
            rec.can_reset = rec.state in ('rejected', 'cancelled') and is_owner

    def _get_applicant_user(self):
        self.ensure_one()
        return self.employee_id.user_id if self.employee_id and self.employee_id.user_id else False

    def _make_notification_body(self, title, message):
        """Return Markup, not raw string, for chatter/html notifications."""
        return Markup('<p><strong>%s</strong></p><p>%s</p>') % (escape(title or ''), escape(message or ''))

    def _notify_users(self, users, title, message, create_activity=False):
        self.ensure_one()
        users = users.filtered(lambda u: u and u.active and u.partner_id)
        if not users:
            return
        body = self._make_notification_body(title, message)
        self.message_post(
            body=body,
            partner_ids=users.mapped('partner_id').ids,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )
        if create_activity:
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            for user in users:
                vals = {
                    'res_model_id': self.env['ir.model']._get_id(self._name),
                    'res_id': self.id,
                    'user_id': user.id,
                    'summary': title,
                    'note': body,
                }
                if activity_type:
                    vals['activity_type_id'] = activity_type.id
                self.env['mail.activity'].sudo().create(vals)

    def _notify_applicant(self, title, message):
        self.ensure_one()
        applicant = self._get_applicant_user()
        if applicant:
            self._notify_users(applicant, title, message, create_activity=False)

    def _done_current_user_activities(self):
        self.activity_ids.filtered(lambda a: a.user_id == self.env.user).action_done()

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Chỉ đơn ở trạng thái Nháp mới được trình duyệt.'))
            if not rec.employee_id.user_id:
                raise UserError(_('Nhân viên làm đơn chưa được liên kết với người dùng Odoo.'))
            if rec.employee_id.user_id != self.env.user:
                raise UserError(_('Bạn chỉ được trình duyệt đơn của chính mình.'))
            if not rec.manager_user_id:
                raise UserError(_('Phòng ban của nhân viên chưa có Trưởng bộ phận hoặc Trưởng bộ phận chưa liên kết User.'))
            rec._check_has_leave_lines()
            rec.state = 'manager_waiting'
            title = _('Đơn xin nghỉ phép cần trưởng bộ phận duyệt')
            message = _('Đơn %s của %s đang chờ trưởng bộ phận duyệt.') % (rec.name, rec.employee_id.name)
            rec._notify_users(rec.manager_user_id, title, message, create_activity=True)
            rec._notify_applicant(_('Đã gửi đơn xin nghỉ phép'), _('Đơn %s đã được gửi đến Trưởng bộ phận.') % rec.name)

    def action_manager_approve(self):
        for rec in self:
            if rec.state != 'manager_waiting':
                raise UserError(_('Đơn không ở bước Trưởng bộ phận duyệt.'))
            if rec.manager_user_id != self.env.user:
                raise UserError(_('Chỉ Trưởng bộ phận của phòng ban mới được duyệt bước này.'))
            rec.write({
                'state': 'hr_waiting',
                'manager_approved_by': self.env.user.id,
                'manager_approved_date': fields.Date.context_today(rec),
            })
            rec._done_current_user_activities()
            hr_users = rec._get_hr_admin_users()
            if not hr_users:
                raise UserError(_('Chưa có người dùng thuộc nhóm Quản trị viên HR.'))
            rec._notify_users(hr_users, _('Đơn xin nghỉ phép cần HR duyệt'), _('Đơn %s đã được Trưởng bộ phận duyệt và đang chờ Quản trị viên HR duyệt.') % rec.name, create_activity=True)
            rec._notify_applicant(_('Trưởng bộ phận đã duyệt'), _('Đơn %s đã được Trưởng bộ phận duyệt và chuyển sang Quản trị viên HR.') % rec.name)

    def action_hr_approve(self):
        for rec in self:
            if rec.state != 'hr_waiting':
                raise UserError(_('Đơn không ở bước Quản trị viên HR duyệt.'))
            if not rec._is_hr_admin(self.env.user):
                raise UserError(_('Chỉ người dùng thuộc nhóm Quản trị viên HR mới được duyệt bước này.'))
            rec.write({
                'state': 'director_waiting',
                'hr_approved_by': self.env.user.id,
                'hr_approved_date': fields.Date.context_today(rec),
            })
            rec._done_current_user_activities()
            director_users = rec._get_director_users()
            if not director_users:
                raise UserError(_('Chưa có người dùng thuộc nhóm Giám Đốc.'))
            rec._notify_users(director_users, _('Đơn xin nghỉ phép cần Giám đốc duyệt'), _('Đơn %s đã được Quản trị viên HR duyệt và đang chờ Giám đốc duyệt.') % rec.name, create_activity=True)
            rec._notify_applicant(_('Quản trị viên HR đã duyệt'), _('Đơn %s đã được Quản trị viên HR duyệt và chuyển sang Giám đốc.') % rec.name)

    def action_director_approve(self):
        for rec in self:
            if rec.state != 'director_waiting':
                raise UserError(_('Đơn không ở bước Giám đốc duyệt.'))
            if not rec._is_director(self.env.user):
                raise UserError(_('Chỉ người dùng thuộc nhóm Giám Đốc mới được duyệt bước này.'))
            rec.write({
                'state': 'approved',
                'director_approved_by': self.env.user.id,
                'director_approved_date': fields.Date.context_today(rec),
            })
            rec._done_current_user_activities()
            rec._notify_applicant(_('Đơn xin nghỉ phép đã được duyệt'), _('Đơn %s đã được Giám đốc duyệt hoàn tất.') % rec.name)
            if rec.handover_employee_id and rec.handover_employee_id.user_id:
                rec._notify_users(rec.handover_employee_id.user_id, _('Thông báo bàn giao công việc'), _('Bạn được chọn là người phụ trách công việc trong thời gian %s nghỉ phép theo đơn %s.') % (rec.employee_id.name, rec.name), create_activity=False)

    def action_open_reject_wizard(self):
        self.ensure_one()
        if not self.can_reject:
            raise UserError(_('Bạn không có quyền từ chối đơn này ở trạng thái hiện tại.'))
        return {
            'name': _('Nhập lý do từ chối'),
            'type': 'ir.actions.act_window',
            'res_model': 'somed.leave.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_leave_request_id': self.id},
        }

    def action_reject_with_reason(self, reason):
        for rec in self:
            if not reason or not reason.strip():
                raise UserError(_('Vui lòng nhập lý do từ chối.'))
            if not rec.can_reject:
                raise UserError(_('Bạn không có quyền từ chối đơn này ở trạng thái hiện tại.'))
            rec.write({'state': 'rejected', 'reject_reason': reason.strip()})
            rec._done_current_user_activities()
            rec._notify_applicant(_('Đơn xin nghỉ phép bị từ chối'), _('Đơn %s đã bị từ chối. Lý do: %s') % (rec.name, reason.strip()))

    def action_cancel(self):
        for rec in self:
            if not rec.can_cancel:
                raise UserError(_('Bạn không có quyền hủy đơn này.'))
            rec.state = 'cancelled'
            rec._notify_applicant(_('Đơn xin nghỉ phép đã hủy'), _('Đơn %s đã được chuyển sang trạng thái Đã hủy.') % rec.name)

    def action_reset_to_draft(self):
        for rec in self:
            if not rec.can_reset:
                raise UserError(_('Bạn không có quyền đưa đơn này về nháp.'))
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
            rec._notify_applicant(_('Đơn xin nghỉ phép đã đưa về nháp'), _('Đơn %s đã được đưa về Nháp.') % rec.name)


class SomedLeaveRequestLine(models.Model):
    _name = 'somed.leave.request.line'
    _description = 'Chi tiết mốc thời gian nghỉ phép'
    _order = 'date_from, id'

    request_id = fields.Many2one('somed.leave.request', string='Đơn xin nghỉ phép', required=True, ondelete='cascade')
    leave_type = fields.Selection([
        ('annual', 'Nghỉ phép'),
        ('sick', 'Nghỉ bệnh'),
        ('unpaid', 'Nghỉ không lương'),
        ('other', 'Khác'),
    ], string='Nội dung', default='annual', required=True)
    date_from = fields.Date(string='Từ ngày', required=True)
    date_to = fields.Date(string='Đến ngày', required=True)
    total_days = fields.Float(string='Tổng ngày nghỉ', compute='_compute_total_days', store=True)
    note = fields.Char(string='Ghi chú')

    @api.depends('date_from', 'date_to')
    def _compute_total_days(self):
        for line in self:
            if line.date_from and line.date_to:
                line.total_days = (line.date_to - line.date_from).days + 1
            else:
                line.total_days = 0

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_to < line.date_from:
                raise ValidationError(_('Đến ngày phải lớn hơn hoặc bằng Từ ngày.'))
