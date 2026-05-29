# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from markupsafe import Markup, escape


def _vietnamese_number_to_words(number):
    try:
        number = int(round(float(number or 0)))
    except Exception:
        number = 0
    if number == 0:
        return 'Không đồng'

    units = ['', 'nghìn', 'triệu', 'tỷ', 'nghìn tỷ', 'triệu tỷ']
    nums = ['không', 'một', 'hai', 'ba', 'bốn', 'năm', 'sáu', 'bảy', 'tám', 'chín']

    def read_three(n, full=False):
        hundred = n // 100
        ten = (n % 100) // 10
        one = n % 10
        words = []
        if full or hundred > 0:
            words.append(nums[hundred])
            words.append('trăm')
        if ten > 1:
            words.append(nums[ten])
            words.append('mươi')
            if one == 1:
                words.append('mốt')
            elif one == 5:
                words.append('lăm')
            elif one > 0:
                words.append(nums[one])
        elif ten == 1:
            words.append('mười')
            if one == 5:
                words.append('lăm')
            elif one > 0:
                words.append(nums[one])
        else:
            if one > 0:
                if full or hundred > 0:
                    words.append('lẻ')
                words.append(nums[one])
        return ' '.join(words)

    groups = []
    n = number
    while n > 0:
        groups.append(n % 1000)
        n //= 1000

    parts = []
    for idx in range(len(groups) - 1, -1, -1):
        group = groups[idx]
        if group == 0:
            continue
        full = idx < len(groups) - 1 and group < 100
        part = read_three(group, full=full)
        unit = units[idx] if idx < len(units) else ''
        parts.append((part + (' ' + unit if unit else '')).strip())
    result = ' '.join(parts).strip()
    return result[:1].upper() + result[1:] + ' đồng'


class SomedAdvanceRequest(models.Model):
    _name = 'somed.advance.request'
    _description = 'Giấy đề nghị tạm ứng'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Số phiếu', default='New', copy=False, readonly=True, tracking=True)
    request_date = fields.Date(string='Ngày đề nghị', default=fields.Date.context_today, required=True, tracking=True)
    employee_id = fields.Many2one('hr.employee', string='Người tạm ứng', default=lambda self: self._default_employee(), required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Người dùng', related='employee_id.user_id', store=True, readonly=True)
    department_id = fields.Many2one('hr.department', string='Đơn vị công tác', related='employee_id.department_id', store=True, readonly=True)
    job_id = fields.Many2one('hr.job', string='Chức vụ', related='employee_id.job_id', store=True, readonly=True)

    manager_id = fields.Many2one('hr.employee', string='Trưởng bộ phận', compute='_compute_manager', store=True)
    manager_user_id = fields.Many2one('res.users', string='User trưởng bộ phận', compute='_compute_manager', store=True)

    reason = fields.Text(string='Lý do tạm ứng', required=True, tracking=True)
    advance_document = fields.Char(string='Chứng từ tạm ứng', tracking=True)
    amount = fields.Monetary(string='Số tiền tạm ứng kỳ này', required=True, tracking=True)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', default=lambda self: self.env.company.currency_id.id, required=True)
    amount_text = fields.Char(string='Bằng chữ', compute='_compute_amount_text', store=True, readonly=False)

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('manager_waiting', 'Chờ trưởng bộ phận duyệt'),
        ('accountant_waiting', 'Chờ kế toán tổng hợp duyệt'),
        ('director_waiting', 'Chờ giám đốc duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
        ('cancelled', 'Đã hủy'),
    ], string='Trạng thái', default='draft', tracking=True, required=True)

    manager_approved_by = fields.Many2one('res.users', string='Trưởng bộ phận đã duyệt', readonly=True, copy=False)
    manager_approved_date = fields.Date(string='Ngày trưởng bộ phận duyệt', readonly=True, copy=False)
    accountant_approved_by = fields.Many2one('res.users', string='Kế toán tổng hợp đã duyệt', readonly=True, copy=False)
    accountant_approved_date = fields.Date(string='Ngày kế toán tổng hợp duyệt', readonly=True, copy=False)
    director_approved_by = fields.Many2one('res.users', string='Giám đốc đã duyệt', readonly=True, copy=False)
    director_approved_date = fields.Date(string='Ngày giám đốc duyệt', readonly=True, copy=False)

    reject_reason = fields.Text(string='Lý do từ chối', readonly=True, copy=False, tracking=True)

    payment_request_id = fields.Many2one(
        'account.payment.request',
        string='Phiếu chi',
        readonly=True,
        copy=False,
        ondelete='set null',
        tracking=True,
    )
    payment_request_state = fields.Selection(
        related='payment_request_id.state',
        string='Trạng thái phiếu chi',
        store=True,
        readonly=True,
    )
    payment_request_status_expense = fields.Selection(
        related='payment_request_id.status_expense',
        string='Tình trạng chi',
        store=True,
        readonly=True,
    )
    payment_date = fields.Date(
        related='payment_request_id.date_payment',
        string='Ngày chi tiền',
        store=True,
        readonly=True,
    )
    payment_request_count = fields.Integer(
        string='Số phiếu chi',
        compute='_compute_payment_request_count',
    )

    can_submit = fields.Boolean(compute='_compute_button_visibility')
    can_manager_approve = fields.Boolean(compute='_compute_button_visibility')
    can_accountant_approve = fields.Boolean(compute='_compute_button_visibility')
    can_director_approve = fields.Boolean(compute='_compute_button_visibility')
    can_reject = fields.Boolean(compute='_compute_button_visibility')
    can_cancel = fields.Boolean(compute='_compute_button_visibility')
    can_reset = fields.Boolean(compute='_compute_button_visibility')
    can_create_payment_request = fields.Boolean(compute='_compute_button_visibility')

    @api.model
    def _default_employee(self):
        return self.env['hr.employee'].search([('user_id', '=', self.env.uid)], limit=1)

    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env['ir.sequence']
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = seq.next_by_code('somed.advance.request') or 'New'
        return super().create(vals_list)

    @api.depends('employee_id.department_id.manager_id', 'employee_id.department_id.manager_id.user_id')
    def _compute_manager(self):
        for rec in self:
            manager = rec.employee_id.department_id.manager_id if rec.employee_id and rec.employee_id.department_id else False
            rec.manager_id = manager
            rec.manager_user_id = manager.user_id if manager else False

    @api.depends('amount')
    def _compute_amount_text(self):
        for rec in self:
            rec.amount_text = _vietnamese_number_to_words(rec.amount)

    def _is_director(self):
        group = self.env.ref('custom_director_role.group_director', raise_if_not_found=False)
        return bool(group and group in self.env.user.groups_id)

    def _get_director_users(self):
        group = self.env.ref('custom_director_role.group_director', raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    def _is_accountant_manager(self):
        group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        return bool(group and group in self.env.user.groups_id)

    def _get_accountant_manager_users(self):
        group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        return group.users if group else self.env['res.users']

    @api.depends('state', 'manager_user_id', 'user_id', 'payment_request_id')
    def _compute_button_visibility(self):
        user = self.env.user
        is_accountant = self._is_accountant_manager()
        is_director = self._is_director()
        for rec in self:
            is_owner = rec.user_id == user
            is_manager = rec.manager_user_id == user
            rec.can_submit = rec.state == 'draft' and is_owner
            rec.can_manager_approve = rec.state == 'manager_waiting' and is_manager
            rec.can_accountant_approve = rec.state == 'accountant_waiting' and is_accountant
            rec.can_director_approve = rec.state == 'director_waiting' and is_director
            rec.can_reject = (
                (rec.state == 'manager_waiting' and is_manager) or
                (rec.state == 'accountant_waiting' and is_accountant) or
                (rec.state == 'director_waiting' and is_director)
            )
            rec.can_cancel = rec.state in ('draft', 'manager_waiting') and is_owner
            rec.can_reset = rec.state in ('rejected', 'cancelled') and is_owner
            rec.can_create_payment_request = (
                rec.state in ('director_waiting', 'approved')
                and is_accountant
                and not rec.payment_request_id
            )

    def _compute_payment_request_count(self):
        for rec in self:
            rec.payment_request_count = 1 if rec.payment_request_id else 0

    def _get_employee_partner(self):
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return False
        # Odoo 17 thường dùng work_contact_id; một số DB cũ dùng address_home_id.
        if 'work_contact_id' in employee._fields and employee.work_contact_id:
            return employee.work_contact_id
        if 'address_home_id' in employee._fields and employee.address_home_id:
            return employee.address_home_id
        if employee.user_id and employee.user_id.partner_id:
            return employee.user_id.partner_id
        return False

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount <= 0:
                raise ValidationError(_('Số tiền tạm ứng phải lớn hơn 0.'))

    def _ensure_owner(self):
        for rec in self:
            if rec.user_id != self.env.user:
                raise UserError(_('Bạn chỉ được thao tác trên phiếu tạm ứng của chính mình.'))

    def _ensure_manager(self):
        for rec in self:
            if rec.manager_user_id != self.env.user:
                raise UserError(_('Chỉ trưởng bộ phận của nhân viên mới được duyệt bước này.'))

    def _ensure_accountant_manager(self):
        if not self._is_accountant_manager():
            raise UserError(_('Chỉ Quản trị viên Kế toán mới được duyệt bước kế toán tổng hợp.'))

    def _ensure_director(self):
        if not self._is_director():
            raise UserError(_('Chỉ Giám đốc mới được duyệt bước này.'))

    def _format_html(self, title, message):
        return Markup('<p><strong>%s</strong></p><p>%s</p>') % (escape(title or ''), escape(message or ''))

    def _post_to_record(self, title, message, partner_ids=None):
        self.ensure_one()
        partners = []
        for partner in partner_ids or []:
            if partner:
                partners.append(partner.id)
        self.message_post(body=self._format_html(title, message), partner_ids=partners)

    def _notify_user(self, user, title, message, create_activity=False):
        self.ensure_one()
        if not user or not user.partner_id:
            return
        self._post_to_record(title, message, [user.partner_id])
        if create_activity:
            activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if activity_type:
                self.activity_schedule(
                    activity_type_id=activity_type.id,
                    user_id=user.id,
                    summary=title,
                    note=self._format_html(title, message),
                    date_deadline=fields.Date.context_today(self),
                )

    def _notify_users(self, users, title, message, create_activity=False):
        for user in users:
            self._notify_user(user, title, message, create_activity=create_activity)

    def _notify_applicant(self, title, message):
        self.ensure_one()
        self._notify_user(self.user_id, title, message, create_activity=False)


    def _close_all_activities(self, feedback=None):
        """Đóng toàn bộ activity đang mở của phiếu.

        Dùng khi một bước đã được xử lý bởi một người trong nhóm duyệt
        để các activity trùng lặp của những người cùng nhóm không còn treo nữa.
        """
        Activity = self.env['mail.activity'].sudo()
        for rec in self:
            activities = Activity.search([
                ('res_model', '=', rec._name),
                ('res_id', '=', rec.id),
            ])
            if activities:
                activities.action_feedback(feedback=feedback or _('Đã xử lý'))

    def _validate_before_submit(self):
        for rec in self:
            if not rec.employee_id:
                raise UserError(_('Không tìm thấy nhân viên của người dùng hiện tại.'))
            if not rec.user_id:
                raise UserError(_('Nhân viên này chưa gắn người dùng Odoo.'))
            if not rec.department_id:
                raise UserError(_('Nhân viên chưa có phòng ban/đơn vị công tác.'))
            if not rec.manager_id:
                raise UserError(_('Phòng ban của nhân viên chưa khai báo Trưởng bộ phận.'))
            if not rec.manager_user_id:
                raise UserError(_('Trưởng bộ phận chưa được gắn người dùng Odoo.'))
            if not self._get_accountant_manager_users():
                raise UserError(_('Chưa có người dùng thuộc nhóm Kế toán / Administrator để duyệt bước kế toán tổng hợp.'))
            if not self._get_director_users():
                raise UserError(_('Chưa có người dùng thuộc nhóm Giám Đốc.'))

    def action_submit(self):
        for rec in self:
            rec._ensure_owner()
            if rec.state != 'draft':
                raise UserError(_('Chỉ phiếu nháp mới được trình duyệt.'))
            rec._validate_before_submit()

            # Nếu người tạm ứng đồng thời là Trưởng bộ phận của chính phòng ban,
            # tự ghi nhận bước Trưởng bộ phận là người đó đã duyệt rồi chuyển sang Kế toán tổng hợp.
            if rec.manager_user_id and rec.manager_user_id == rec.user_id:
                today = fields.Date.context_today(rec)
                rec.write({
                    'state': 'accountant_waiting',
                    'manager_approved_by': rec.user_id.id,
                    'manager_approved_date': today,
                })
                rec._notify_applicant(
                    _('Đã gửi phiếu tạm ứng'),
                    _('Phiếu %s đã được gửi. Vì người tạm ứng là Trưởng bộ phận của chính phòng ban nên hệ thống đã tự ghi nhận Trưởng bộ phận duyệt và chuyển sang Kế toán tổng hợp.') % rec.name
                )
                rec._notify_users(
                    rec._get_accountant_manager_users(),
                    _('Phiếu tạm ứng cần kế toán tổng hợp duyệt'),
                    _('Phiếu %s của %s đã được Trưởng bộ phận tự xác nhận và đang chờ Kế toán tổng hợp duyệt.') % (rec.name, rec.employee_id.name),
                    create_activity=True,
                )
                continue

            rec.write({'state': 'manager_waiting'})
            title = _('Phiếu tạm ứng cần trưởng bộ phận duyệt')
            msg = _('Phiếu %s của %s đang chờ trưởng bộ phận duyệt.') % (rec.name, rec.employee_id.name)
            rec._notify_user(rec.manager_user_id, title, msg, create_activity=True)
            rec._notify_applicant(_('Đã gửi phiếu tạm ứng'), _('Phiếu %s đã được gửi và đang chờ trưởng bộ phận duyệt.') % rec.name)

    def action_manager_approve(self):
        for rec in self:
            rec._ensure_manager()
            if rec.state != 'manager_waiting':
                raise UserError(_('Phiếu không ở trạng thái chờ trưởng bộ phận duyệt.'))
            rec.write({
                'state': 'accountant_waiting',
                'manager_approved_by': self.env.user.id,
                'manager_approved_date': fields.Date.context_today(rec),
            })
            rec._close_all_activities(_('Trưởng bộ phận đã duyệt'))
            rec._notify_applicant(_('Trưởng bộ phận đã duyệt'), _('Phiếu %s đã được trưởng bộ phận duyệt và chuyển sang kế toán tổng hợp.') % rec.name)
            rec._notify_users(
                rec._get_accountant_manager_users(),
                _('Phiếu tạm ứng cần kế toán tổng hợp duyệt'),
                _('Phiếu %s của %s đang chờ kế toán tổng hợp duyệt.') % (rec.name, rec.employee_id.name),
                create_activity=True,
            )

    def action_accountant_approve(self):
        self._ensure_accountant_manager()
        for rec in self:
            if rec.state != 'accountant_waiting':
                raise UserError(_('Phiếu không ở trạng thái chờ kế toán tổng hợp duyệt.'))
            rec.write({
                'state': 'director_waiting',
                'accountant_approved_by': self.env.user.id,
                'accountant_approved_date': fields.Date.context_today(rec),
            })
            rec._close_all_activities(_('Kế toán tổng hợp đã duyệt'))
            rec._notify_applicant(_('Kế toán tổng hợp đã duyệt'), _('Phiếu %s đã được kế toán tổng hợp duyệt và chuyển sang giám đốc.') % rec.name)
            rec._notify_users(
                rec._get_director_users(),
                _('Phiếu tạm ứng cần giám đốc duyệt'),
                _('Phiếu %s của %s đang chờ giám đốc duyệt.') % (rec.name, rec.employee_id.name),
                create_activity=True,
            )

    def action_director_approve(self):
        self._ensure_director()
        for rec in self:
            if rec.state != 'director_waiting':
                raise UserError(_('Phiếu không ở trạng thái chờ giám đốc duyệt.'))
            rec.write({
                'state': 'approved',
                'director_approved_by': self.env.user.id,
                'director_approved_date': fields.Date.context_today(rec),
            })
            rec._close_all_activities(_('Giám đốc đã duyệt'))
            rec._notify_applicant(_('Phiếu tạm ứng đã được duyệt hoàn tất'), _('Phiếu %s đã được giám đốc duyệt hoàn tất.') % rec.name)

    def action_open_reject_wizard(self):
        self.ensure_one()
        if not self.can_reject:
            raise UserError(_('Bạn không có quyền từ chối phiếu này.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Từ chối phiếu tạm ứng'),
            'res_model': 'somed.advance.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_advance_id': self.id},
        }

    def action_reject_with_reason(self, reason):
        for rec in self:
            if not rec.can_reject:
                raise UserError(_('Bạn không có quyền từ chối phiếu này.'))
            rec.write({'state': 'rejected', 'reject_reason': reason})
            rec._close_all_activities(_('Phiếu tạm ứng đã bị từ chối'))
            rec._notify_applicant(_('Phiếu tạm ứng bị từ chối'), _('Phiếu %s đã bị từ chối. Lý do: %s') % (rec.name, reason))

    def action_cancel(self):
        for rec in self:
            rec._ensure_owner()
            if rec.state not in ('draft', 'manager_waiting'):
                raise UserError(_('Chỉ được hủy phiếu ở trạng thái nháp hoặc chờ trưởng bộ phận duyệt.'))
            rec.write({'state': 'cancelled'})
            rec._close_all_activities(_('Phiếu tạm ứng đã hủy'))
            rec._notify_applicant(_('Phiếu tạm ứng đã hủy'), _('Phiếu %s đã được hủy.') % rec.name)

    def action_reset_to_draft(self):
        for rec in self:
            rec._ensure_owner()
            if rec.state not in ('rejected', 'cancelled'):
                raise UserError(_('Chỉ phiếu bị từ chối hoặc đã hủy mới được đưa về nháp.'))
            rec.write({
                'state': 'draft',
                'reject_reason': False,
                'manager_approved_by': False,
                'manager_approved_date': False,
                'accountant_approved_by': False,
                'accountant_approved_date': False,
                'director_approved_by': False,
                'director_approved_date': False,
            })
            rec._close_all_activities(_('Phiếu tạm ứng đã đưa về nháp'))
            rec._notify_applicant(_('Phiếu tạm ứng đã đưa về nháp'), _('Phiếu %s đã được đưa về nháp.') % rec.name)

    def _prepare_payment_request_vals(self):
        self.ensure_one()
        partner = self._get_employee_partner()
        note = (
            'Chi tiền tạm ứng theo phiếu %s\n'
            'Người tạm ứng: %s\n'
            'Lý do: %s'
        ) % (self.name, self.employee_id.name or '', self.reason or '')

        line_vals = {
            'line_type': 'advance',
            'advance_request_id': self.id,
            'amount': self.amount,
            'interpretation': 'Tạm ứng %s - %s' % (self.name, (self.reason or '')[:120]),
            'note': self.advance_document or False,
        }

        vals = {
            'payment_kind': 'advance',
            'advance_request_id': self.id,
            'manual_total': self.amount,
            'date': self.request_date or fields.Date.context_today(self),
            'receive_person': partner.id if partner else False,
            'currency_id': self.currency_id.id if self.currency_id else self.env.company.currency_id.id,
            'cost_classification': 'employee',
            'payment_type': 'cash',
            'note': note,
            'line_ids': [(0, 0, line_vals)],
        }

        # Một số database có field proposal_person_id là res.users.
        if 'proposal_person_id' in self.env['account.payment.request']._fields:
            vals['proposal_person_id'] = self.user_id.id if self.user_id else False

        return vals

    def action_create_payment_request(self):
        self._ensure_accountant_manager()
        PaymentRequest = self.env['account.payment.request']

        for rec in self:
            if rec.state not in ('director_waiting', 'approved'):
                raise UserError(_('Chỉ phiếu tạm ứng đã được Kế toán tổng hợp duyệt mới được tạo phiếu chi.'))
            if rec.payment_request_id:
                return rec.action_view_payment_request()
            if rec.amount <= 0:
                raise UserError(_('Số tiền tạm ứng phải lớn hơn 0.'))

            payment = PaymentRequest.create(rec._prepare_payment_request_vals())
            rec.write({'payment_request_id': payment.id})

            rec.message_post(
                body=Markup('<p>Đã tạo phiếu chi <strong>%s</strong> cho phiếu tạm ứng này.</p>') % escape(payment.name or ''),
                subtype_xmlid='mail.mt_comment',
            )
            payment.message_post(
                body=Markup('<p>Phiếu chi này được tạo từ phiếu tạm ứng <strong>%s</strong>.</p>') % escape(rec.name or ''),
                subtype_xmlid='mail.mt_comment',
            )

            rec._notify_applicant(
                _('Đã tạo phiếu chi cho phiếu tạm ứng'),
                _('Phiếu %s đã được kế toán tạo phiếu chi %s.') % (rec.name, payment.name),
            )

            # Nếu phiếu chi được tạo ngay sau bước Kế toán tổng hợp duyệt,
            # phiếu tạm ứng vẫn tiếp tục nằm ở trạng thái chờ Giám đốc duyệt.
            # Kế toán có thể xử lý chi tiền trước/sau tùy quy trình nội bộ.


            return {
                'type': 'ir.actions.act_window',
                'name': _('Phiếu chi'),
                'res_model': 'account.payment.request',
                'view_mode': 'form',
                'res_id': payment.id,
                'target': 'current',
            }

    def action_view_payment_request(self):
        self.ensure_one()
        if not self.payment_request_id:
            raise UserError(_('Phiếu tạm ứng này chưa có phiếu chi.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Phiếu chi'),
            'res_model': 'account.payment.request',
            'view_mode': 'form',
            'res_id': self.payment_request_id.id,
            'target': 'current',
        }

    def action_print_pdf(self):
        self.ensure_one()
        return self.env.ref('hr_advance_request_full.action_report_somed_advance_request').report_action(self)
