from markupsafe import Markup
from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)

class ProposalSheet(models.Model):
    _name = 'proposal.sheet'
    _description = 'Phiếu Đề Xuất'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    department_id = fields.Many2one('hr.department', string='Phòng Ban', required=True)
    manager_id = fields.Many2one('hr.employee', string='Người Quản Lý', compute='_compute_manager_id')
    director_user_id = fields.Many2one('res.users', string="Giám Đốc", default=lambda self: self._default_director_user(), readonly=True)
    name = fields.Char(string='Mã Đề Xuất', default='New', readonly=True, copy=False)
    project_id = fields.Many2one('project.project', string='Dự án', required=True, tracking=True)
    task_id = fields.Many2one('project.task', string='Nhiệm Vụ', required=True, tracking=True)
    requested_by = fields.Many2one('res.users', string='Người Đề Xuất', default=lambda self: self.env.user, readonly=True, tracking=True)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('reviewed_manager', 'Đang phê duyệt (QL)'),
        ('reviewed_accounting', 'Đang phê duyệt (KT)'),
        ('approved', 'Đang phê duyệt (Sếp)'),
        ('waiting_accounting_paid', 'Chờ chi tiền (KT)'),
        ('done', 'Hoàn tất'),
        ('rejected', 'Bị từ chối'),
        ('canceled', 'Đã hủy'),
    ], string="Trạng thái", default='draft', tracking=True)

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
    amount_total = fields.Float(string='Tổng Thành Tiền', compute='_compute_amount_total', store=True)
    take_note = fields.Text(string='Ghi Chú', tracking=True)
    @api.model
    def _default_director_user(self):
        group = self.env.ref('custom_director_role.group_director')  # đổi lại module ID cho đúng
        users = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1)
        return users.id if users else False
    @api.depends('department_id')
    def _compute_manager_id(self):
        for record in self:
            record.manager_id = record.department_id.manager_id if record.department_id else False
    @api.depends('type', 'material_line_ids.price_total', 'expense_line_ids.price_total')
    def _compute_amount_total(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total = sum(line.price_total for line in sheet.material_line_ids)
            elif sheet.type == 'expense':
                sheet.amount_total = sum(line.price_total for line in sheet.expense_line_ids)
            else:
                sheet.amount_total = 0.0
    show_button_submit = fields.Boolean(compute='_compute_show_buttons')
    show_button_manager_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_accounting_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_boss_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_waiting_accounting_paid = fields.Boolean(compute='_compute_show_buttons')
    show_button_done = fields.Boolean(compute='_compute_show_buttons')
    show_button_reject = fields.Boolean(compute='_compute_show_buttons')
    show_button_cancel = fields.Boolean(compute='_compute_show_buttons')
    show_button_reset_draft = fields.Boolean(compute='_compute_show_buttons')
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
        record = super().create(vals) 
        return record

    def write(self, vals):
        for rec in self:
            # Chỉ kiểm tra nếu trong vals có type VÀ nó khác type hiện tại
            if 'type' in vals and vals['type'] != rec.type:
                if rec.material_line_ids or rec.expense_line_ids:
                    raise ValidationError(
                        "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí."
                    )           
        res = super(ProposalSheet, self).write(vals)
        return res
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
                
    def _send_notification(self, message, partner_ids=None):
        """
        Gửi thông báo vào Chatter + Discuss.
        :param message: Nội dung thông báo (HTML)
        :param partner_ids: Danh sách partner_id nhận thông báo (list[int])
        """
        self.ensure_one()

        if partner_ids is None:
            partner_ids = []
        for rec in self:
            rec.message_follower_ids.sudo().unlink()
        # Đảm bảo tất cả partner_ids đều là follower
        existing_followers = self.message_partner_ids.ids
        new_partners = [pid for pid in partner_ids if pid not in existing_followers]
        if new_partners:
            self.message_subscribe(partner_ids=new_partners)

        # Post vào Chatter và gửi Discuss
        self.message_post(
            body=Markup(message),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids
        )
    def _get_approval_partners(self, include_manager, include_boss, include_accounting):
        """
        Trả về danh sách partner_ids của PM và Boss theo cấu hình Project.
        :param include_manager: Có lấy PM không
        :param include_boss: Có lấy Boss không
        :return: list partner_ids
        """
        partner_ids = []
        partner_ids.append(self.requested_by.partner_id.id)  # Người đề xuất luôn nhận thông báo
        for rec in self:
            if include_manager and rec.department_id:
                partner_ids.append(rec.manager_id.user_id.partner_id.id)
            if include_boss and rec.director_user_id:
                partner_ids.append(rec.director_user_id.partner_id.id)
            # Kế toán: tìm tất cả người dùng thuộc nhóm kế toán
            accounting_group = self.env.ref('account.group_account_manager')  # group kế toán mặc định
            accounting_users = accounting_group.users
            if include_accounting and accounting_users:
                # Lấy partner_id của tất cả người dùng trong nhóm kế toán
                partner_ids.extend(user.partner_id.id for user in accounting_users if user.partner_id.id not in partner_ids)
        return partner_ids

    def action_submit(self):
        self.ensure_one()

        # 1. Kiểm tra bắt buộc có dòng trước khi submit
        if self.type == 'material' and not self.material_line_ids:
            raise ValidationError(_("Phiếu đề xuất vật tư phải có ít nhất một dòng vật tư trước khi gửi duyệt."))
        if self.type == 'expense' and not self.expense_line_ids:
            raise ValidationError(_("Phiếu đề xuất chi phí phải có ít nhất một dòng chi phí trước khi gửi duyệt."))

        # 2. Kiểm tra trạng thái
        if self.state != 'draft':
            raise UserError(_("Chỉ phiếu ở trạng thái nháp mới được gửi duyệt."))

        # 3. Đổi trạng thái
        if self.manager_id.user_id == self.env.user:
            self.state = 'reviewed_accounting'
            _logger.info(">>> Proposal %s chuyển sang trạng thái 'reviewed_accounting'", self.name)

            partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
            message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi <em>{self.env.user.name}</em>.</p>"
            self._send_notification(message, partner_ids)
        else:
            self.state = 'reviewed_manager'
            _logger.info(">>> Proposal %s chuyển sang trạng thái 'reviewed_manager'", self.name)

            partner_ids = self._get_approval_partners(include_manager=True, include_boss=False, include_accounting=False)
            message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi <em>{self.env.user.name}</em>.</p>"
            self._send_notification(message, partner_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def action_manager_approve(self):
        if self.state != 'reviewed_manager':
            raise UserError("Chỉ phiếu đang xem xét mới được duyệt.")
        self.state = 'reviewed_accounting'
        approver_name = self.env.user.name
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được duyệt bởi <em>{approver_name}</em>.</p>"
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
        self._send_notification(message, partner_ids)


    def action_boss_approve(self):
        for record in self:
            if record.state != 'approved':
                raise UserError("Chỉ phiếu đang ở trạng thái đang phê duyệt mới được gửi kế toán.")
        self.state = 'waiting_accounting_paid'
        # Gửi thông báo đến kế toán
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được duyệt bởi <em>{self.env.user.name}</em>.</p>"
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
        self._send_notification(message, partner_ids)

    def action_waiting_accounting_paid(self):
        if self.state != 'waiting_accounting_paid':
            raise UserError("Chỉ phiếu đã phê duyệt mới được hoàn tất.")
        # Chuyển sang trạng thái chờ kế toán chi tiền
        payment_request = self.env['account.payment.request'].search([('proposal_sheet_id', '=', self.id)], limit=1)
        for record in self:
            existing = payment_request
            if not existing:
                payment_request= self.env['account.payment.request'].create({
                    'proposal_sheet_id': record.id,
                    'total': record.amount_total,
                    'date': record.create_date,
                    'project_id': record.project_id.id,
                    'proposal_person_id': record.requested_by.id,
                    # 'journal_id': record.journal_id.id,
                })
        
        # self.state = 'waiting_accounting_paid'
        # message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> chờ chi tiền.</p>"        
        # partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=False)
        # self._send_notification(message, partner_ids)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Request',
            'res_model': 'account.payment.request',
            'view_mode': 'form',
            'res_id': payment_request.id,
            'target': 'current',  # hoặc 'new' nếu muốn mở trong popup
        }
    def action_accounting_approve(self):
        if self.state != 'reviewed_accounting':
            raise UserError("Chỉ phiếu đã được Quản lý duyệt mới được Kế toán duyệt.")
        self.state = 'approved'
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được duyệt bởi <em>{self.env.user.name}</em>.</p>"        
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=True, include_accounting=False)
        # Gửi thông báo đến giám đốc
        self._send_notification(message, partner_ids)
    def action_reset_to_draft(self):
        if self.state != 'rejected':
            raise UserError("Chỉ phiếu bị từ chối mới được reset về nháp.")
        self.state = 'draft'
        self.message_post(body="Phiếu được reset về Nháp.")
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    def action_cancel(self):
        for rec in self:
            if rec.state in ['done', 'canceled']:
                raise UserError("Không thể hủy phiếu đã hoàn tất hoặc đã hủy.")
            rec.state = 'canceled'
            
            rec.message_post(body="Phiếu đã được hủy.")
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
            
            
        

    @api.depends('state', 'task_id.project_id.user_id')
    def _compute_show_buttons(self):
        for rec in self:
            is_creator = rec.requested_by == self.env.user
            is_manager = rec.manager_id.user_id == self.env.user
            is_accounting = self.env.user.has_group('account.group_account_manager')  # KT
            is_boss = rec.director_user_id == self.env.user

            # rec.show_button_submit = rec.state == 'draft' and is_creator
            # rec.show_button_manager_approve = rec.state == 'submitted' and is_manager
            # rec.show_button_accounting_approve = rec.state == 'reviewed_manager' and is_accounting
            # rec.show_button_boss_approve = rec.state == 'reviewed_accounting' and is_boss
            # rec.show_button_done = rec.state == 'approved' and is_accounting  # KT chi xong
            # rec.show_button_reject = rec.state in ['submitted', 'reviewed_manager', 'reviewed_accounting', 'approved'] \
            #                         and (is_manager or is_accounting or is_boss)
            # rec.show_button_cancel = rec.state in ['draft', 'submitted'] and is_creator
            # rec.show_button_reset_draft = rec.state == 'rejected' and is_creator
            
            rec.show_button_submit = rec.state == 'draft' and is_creator
            rec.show_button_manager_approve = rec.state == 'reviewed_manager' and is_manager
            rec.show_button_accounting_approve = rec.state == 'reviewed_accounting' and is_accounting
            rec.show_button_boss_approve = rec.state == 'approved' and is_boss
            rec.show_button_waiting_accounting_paid = rec.state == 'waiting_accounting_paid' and is_accounting
            rec.show_button_done = rec.state == 'done' and is_accounting
            rec.show_button_reject = (
                (rec.state == 'reviewed_manager' and is_manager) or
                (rec.state == 'reviewed_accounting' and is_accounting) or
                (rec.state == 'approved' and is_boss)
            )
            rec.show_button_cancel = rec.state in ['draft'] and is_creator
            rec.show_button_reset_draft = rec.state == 'rejected' and is_creator
    

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
        default=lambda self: self.env['hr.department'].get_manager_id_by_name('Administration').user_id.id if self.env['hr.department'].get_manager_id_by_name('Administration') else False,
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
    def action_view_pdf(self):
        self.ensure_one()
        filename = f"Phieu_De_Xuat_{self.name}.pdf"
        return {
            'type': 'ir.actions.act_url',
            'url': f'/report/pdf/proposal_sheet.report_proposal_sheet_template/{self.id}?filename={filename}',
            'target': 'new',
        }