from markupsafe import Markup
from odoo import models, fields, api,_
from odoo.exceptions import UserError, ValidationError
from lxml import etree
import logging
from datetime import timedelta

_logger = logging.getLogger(__name__)

class ProposalSheet(models.Model):
    _name = 'proposal.sheet'
    _description = 'Phiếu Đề Xuất'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc"
    department_id = fields.Many2one('hr.department', string='Phòng Ban', required=True,default=lambda self: self.env.user.employee_id.department_id.id)
    manager_id = fields.Many2one('hr.employee', string='Người Quản Lý', compute='_compute_manager_id')
    director_user_id = fields.Many2one('res.users', string="Giám Đốc", default=lambda self: self._default_director_user(), readonly=True)
    name = fields.Char(string='Mã Đề Xuất', default='New', readonly=True, copy=False)
    project_id = fields.Many2one('project.project', string='Dự án', tracking=True)
    task_id = fields.Many2one('project.task', string='Nhiệm Vụ', tracking=True)
    requested_by = fields.Many2one('res.users', string='Người Đề Xuất', default=lambda self: self.env.user, readonly=True, tracking=True)
    treasurer_confirmed = fields.Boolean(string="Thủ quỹ đã xác nhận", default=False)
    currency_id = fields.Many2one('res.currency', string='Tiền tệ', required=True, default=lambda self: self.env.company.currency_id)
    state = fields.Selection([
        ('draft', 'Nháp'),
        ('reviewed_manager', 'QL Đang trình'),
        ('reviewed_accounting', 'KTTH Đang kiểm tra'),
        ('approved', 'Sếp Đang duyệt'),
        ('waiting_accounting_paid', 'Chờ KT xử lý'),
        ('done', 'Hoàn tất'),
        ('rejected', 'Bị từ chối'),
        ('canceled', 'Đã hủy'),
    ], string="Trạng thái", default='draft')
    stock_location_id = fields.Many2one(
        'stock.location',
        string='Vị trí kho kiểm kê',
        domain="[('usage', '=', 'internal')]",
        default=lambda self: self._default_stock_location_id(),
        tracking=True,
    )
    stock_check_done = fields.Boolean(string='Đã xác nhận tồn thực tế', default=False, copy=False)
    stock_checked_by = fields.Many2one('res.users', string='Người xác nhận tồn', copy=False, readonly=True)
    stock_checked_date = fields.Datetime(string='Ngày xác nhận tồn', copy=False, readonly=True)
    cost_additional_expense_line_id = fields.Many2one(
    'cost.additional.expense.line',
    string='Dòng chi phí bổ sung',
    domain="[('project_id', '=', project_id)]",
    help="Chọn dòng chi phí bổ sung liên quan đến dự án này."
)
    date_proposal = fields.Date(string='Ngày Đề Xuất')
    date_reviewed_manager = fields.Date(string='Ngày QL duyệt')
    date_reviewed_accounting = fields.Date(string='Ngày KTTH kiểm tra')
    date_approved = fields.Date(string='Ngày Sếp duyệt')
    type = fields.Selection([
        ('material', 'Vật Tư'),
        ('expense', 'Chi Phí Công Trình'),
        ('other', 'Chi phí Khác'),
    ], required=True, string='Loại Đề Xuất',default='material', tracking=True)
    material_line_ids = fields.One2many(
        'proposal.material.line', 'sheet_id',
        string='Chi Tiết Vật Tư',
        domain=[('type', '=', 'material')],
        copy=True
    )
    expense_line_ids = fields.One2many(
        'proposal.expense.line', 'sheet_id',
        string='Chi Tiết Chi Phí Công Trình',
        domain=[('type', '=', 'expense')],
        copy=True
    )
    expense_noproject_line_ids = fields.One2many(
        'proposal.other.expense.line', 'sheet_id',
        string='Chi Tiết Khác',
        domain=[('type', '=', 'other')],
        order='sequence, id', 
        copy=True
    )
    amount_total = fields.Float(string='Tổng Thành Tiền', compute='_compute_amount_total', store=True)
    amount_total_taxes = fields.Float(string='Tổng Thành Tiền (Có Thuế)', compute='_compute_amount_total_taxes', store=True)
    take_note = fields.Text(string='Ghi Chú', tracking=True)
    treasurer_confirmed_note = fields.Char(
        compute='_compute_treasurer_confirmed_note', store=False
    )
    is_new_proposal = fields.Boolean(
    string="Ver mới",
    default=False,
    help="Dòng mới dùng product_id. Các dòng cũ (tạo trước khi nâng cấp) sẽ không được tick và vẫn hiển thị material_id."
)
    contract_num = fields.Char(
    string="Số hợp đồng",
    related="project_id.num_contract",
    store=True,
    readonly=True,
)
    @api.depends('treasurer_confirmed')
    def _compute_treasurer_confirmed_note(self):
        for r in self:
            r.treasurer_confirmed_note = "Thủ quỹ đã xác nhận" if r.treasurer_confirmed else ""
    @api.model
    def _default_stock_location_id(self):
        location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            '|', ('complete_name', 'ilike', 'Nguyên vật liệu'), ('name', 'ilike', 'Nguyên vật liệu')
        ], limit=1)
        if not location:
            location = self.env['stock.location'].search([('usage', '=', 'internal')], limit=1)
        return location.id if location else False

    @api.model
    def _default_director_user(self):
        group = self.env.ref('custom_director_role.group_director')  # đổi lại module ID cho đúng
        users = self.env['res.users'].search([('groups_id', 'in', group.id)], limit=1)
        return users.id if users else False
    @api.depends('department_id')
    def _compute_manager_id(self):
        for record in self:
            record.manager_id = record.department_id.manager_id if record.department_id else False
    @api.depends('type', 'material_line_ids.price_total', 'expense_line_ids.price_total', 'expense_noproject_line_ids.amount')
    def _compute_amount_total(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total = sum(line.price_total for line in sheet.material_line_ids)
            elif sheet.type == 'expense':
                sheet.amount_total = sum(line.price_total for line in sheet.expense_line_ids)
            elif sheet.type == 'other':
                sheet.amount_total = sum(line.amount for line in sheet.expense_noproject_line_ids)
            else:
                sheet.amount_total = 0.0
    @api.depends(
    'type',
    'material_line_ids.price_total_taxed',
    'expense_line_ids.price_unit',
    'expense_noproject_line_ids.amount_tax',
)
    def _compute_amount_total_taxes(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total_taxes = sum(sheet.material_line_ids.mapped('price_total_taxed'))

            elif sheet.type == 'other':
                # ✅ cộng tất cả tiền thuế (dòng không thuế thì amount_tax = 0)
                sheet.amount_total_taxes = sum(sheet.expense_noproject_line_ids.mapped('amount_total'))

            else:
                sheet.amount_total_taxes = sheet.amount_total or 0.0               
    show_button_submit = fields.Boolean(compute='_compute_show_buttons')
    show_button_manager_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_accounting_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_boss_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_waiting_accounting_paid = fields.Boolean(compute='_compute_show_buttons')
    show_button_done = fields.Boolean(compute='_compute_show_buttons')
    show_button_reject = fields.Boolean(compute='_compute_show_buttons')
    show_button_cancel = fields.Boolean(compute='_compute_show_buttons')
    show_button_reset_draft = fields.Boolean(compute='_compute_show_buttons')
    show_button_withdraw_submit = fields.Boolean(compute="_compute_show_buttons")
    show_button_apply_actual_stock = fields.Boolean(compute='_compute_show_buttons')
    show_button_reset_stock_check = fields.Boolean(compute='_compute_show_buttons')
    is_type_readonly = fields.Boolean(compute='_compute_is_type_readonly', store=False)
    cost_estimate_line_ids = fields.Many2many(
    'cost.estimate.line',
    'proposal_sheet_cost_estimate_line_rel',
    'proposal_sheet_id',
    'cost_estimate_line_id',
    string='Hạng mục dự toán',
    domain="[('cost_estimate_id.project_id', '=', project_id)]",
)
    auto_cost_estimate_line_ids = fields.Many2many(
    'cost.estimate.line',
    'proposal_sheet_auto_cost_estimate_line_rel',
    'proposal_sheet_id',
    'cost_estimate_line_id',
    string='Auto hạng mục dự toán',
)
    other_estimate_item = fields.Many2one(
        comodel_name="estimate.item.other",
        string="Hạng mục khác",
    )
    estimate_choice = fields.Selection([
        ("estimate", "Chọn từ dự toán"),
        ("other", "Khác"),
    ], string="Loại hạng mục", default="estimate", required=True)

    @api.onchange('material_line_ids', 'material_line_ids.cost_estimate_line_id')
    def _onchange_cost_estimate_line_ids(self):
        for sheet in self:
            old_auto_ids = set(sheet.auto_cost_estimate_line_ids.ids)
            current_header_ids = set(sheet.cost_estimate_line_ids.ids)
            new_auto_ids = set(sheet.material_line_ids.mapped('cost_estimate_line_id').ids)

            # Phần user chọn tay = header hiện tại trừ phần auto cũ
            manual_ids = current_header_ids - old_auto_ids

            # Header cuối cùng = phần user chọn tay + phần auto mới từ line
            final_ids = manual_ids | new_auto_ids

            sheet.auto_cost_estimate_line_ids = [(6, 0, list(new_auto_ids))]
            sheet.cost_estimate_line_ids = [(6, 0, list(final_ids))]

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalSheet with vals: %s", vals)

        # Xác định type nếu chưa có
        if not vals.get('type'):
            if vals.get('material_line_ids'):
                vals['type'] = 'material'
            elif vals.get('expense_line_ids'):
                vals['type'] = 'expense'
            else:
                raise ValidationError('Vui lòng chọn loại đề xuất trước khi lưu.')

        # Ver mới
        if not vals.get('is_new_proposal'):
            vals['is_new_proposal'] = True

        # --- XỬ LÝ TASK & PROJECT AN TOÀN ---
        task = False

        # 1) Nếu chưa có task_id mà context có default_task_id -> lấy từ đó
        ctx_task_id = self.env.context.get('default_task_id')
        if not vals.get('task_id') and ctx_task_id:
            task = self.env['project.task'].browse(ctx_task_id)
            vals['task_id'] = task.id

        # 2) Nếu chưa có project_id nhưng ĐÃ có task_id -> suy ra project từ task
        if not vals.get('project_id') and vals.get('task_id'):
            # nếu task chưa được set ở trên thì browse lại từ task_id
            task = task or self.env['project.task'].browse(vals['task_id'])
            if task and task.project_id:
                vals['project_id'] = task.project_id.id
        # Nếu vẫn không có project_id thì thôi, cho phép để trống (hoặc bạn muốn thì raise lỗi ở đây)

        # --- SEQUENCE ---
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
            if rec.state not in ('draft', 'canceled','rejected'):
                raise UserError("Chỉ có thể xóa khi phiếu ở trạng thái 'Nháp' hoặc 'Đã hủy' hoặc 'Từ chối'.")
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

    def _check_can_apply_actual_stock(self):
        self.ensure_one()

        if self.type != 'material':
            raise UserError("Chỉ phiếu đề xuất vật tư mới được xác nhận tồn thực tế.")

        if self.state != 'draft':
            raise UserError("Chỉ được xác nhận tồn thực tế khi phiếu đang ở trạng thái nháp.")

        if self.requested_by.id != self.env.user.id:
            raise UserError("Chỉ người đề xuất mới được xác nhận tồn thực tế.")

        if not self.stock_location_id:
            raise UserError("Vui lòng chọn vị trí kho kiểm kê trước khi xác nhận tồn thực tế.")

        if not self.material_line_ids:
            raise UserError("Phiếu chưa có dòng vật tư để xác nhận tồn thực tế.")
    def action_apply_actual_stock(self):
        for rec in self:
            rec._check_can_apply_actual_stock()
            log_items = []

            for line in rec.material_line_ids:
                if not line.product_id:
                    raise UserError(f"Dòng vật tư '{line.display_name}' chưa có sản phẩm nên không thể cập nhật tồn.")
                if line.actual_count_qty < 0:
                    raise UserError(f"Số lượng kiểm kê thực tế của sản phẩm '{line.product_id.display_name}' không được âm.")

                target_qty = line.actual_count_qty or 0.0

                quant = self.env['stock.quant'].sudo().search([
                    ('product_id', '=', line.product_id.id),
                    ('location_id', '=', rec.stock_location_id.id),
                    ('company_id', '=', rec.env.company.id),
                    ('lot_id', '=', False),
                    ('package_id', '=', False),
                    ('owner_id', '=', False),
                ], limit=1)

                old_qty = quant.quantity if quant else 0.0

                if not quant:
                    quant = self.env['stock.quant'].sudo().create({
                        'product_id': line.product_id.id,
                        'location_id': rec.stock_location_id.id,
                        'company_id': rec.env.company.id,
                    })

                # luôn set bằng sudo
                if 'inventory_quantity' in quant._fields:
                    quant.sudo().write({
                        'inventory_quantity': target_qty,
                    })
                elif 'inventory_diff_quantity' in quant._fields:
                    quant.sudo().write({
                        'inventory_diff_quantity': target_qty - (quant.quantity or 0.0),
                    })
                else:
                    raise UserError("Không tìm thấy trường kiểm kê phù hợp trên stock.quant.")

                # luôn apply bằng sudo
                quant.with_context(from_proposal_sheet_actual_stock=True).sudo().action_apply_inventory()

                line.write({
                    'last_counted_qty': target_qty,
                    'last_counted_by': self.env.user.id,
                    'last_counted_date': fields.Datetime.now(),
                })

                log_items.append(
                    f"<li><b>{line.product_id.display_name}</b>: hệ thống {old_qty:g} → thực tế {target_qty:g} (chênh {(target_qty - old_qty):g})</li>"
                )

            rec.sudo().write({
                'stock_check_done': True,
                'stock_checked_by': self.env.user.id,
                'stock_checked_date': fields.Datetime.now(),
            })

            message = (
                f"<p>Đã xác nhận tồn thực tế cho phiếu <strong>{rec.name}</strong> tại kho "
                f"<strong>{rec.stock_location_id.display_name}</strong> bởi <em>{self.env.user.name}</em>.</p>"
                f"<ul>{''.join(log_items)}</ul>"
            )
            rec.message_post(body=Markup(message))

        return {'type': 'ir.actions.client', 'tag': 'reload'}
    def action_reset_stock_check(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Chỉ được reset xác nhận tồn khi phiếu đang ở trạng thái nháp.")
            if rec.requested_by != self.env.user:
                raise UserError("Chỉ người đề xuất mới được reset xác nhận tồn.")

            rec.material_line_ids.write({
                'actual_count_qty': 0.0,
                'count_note': False,
                'last_counted_qty': 0.0,
                'last_counted_by': False,
                'last_counted_date': False,
            })
            rec.write({
                'stock_check_done': False,
                'stock_checked_by': False,
                'stock_checked_date': False,
            })
            rec.message_post(body="Đã reset thông tin kiểm kê thực tế trên phiếu đề xuất.")

        return {'type': 'ir.actions.client', 'tag': 'reload'}

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

        if self.type == 'material' and not self.stock_check_done:
            raise ValidationError(_("Phiếu vật tư phải được xác nhận tồn thực tế trước khi gửi duyệt."))
        accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        is_accounting_user = accounting_group and accounting_group in self.env.user.groups_id

        # ===== CASE 1: Người gửi là Kế toán -> Gửi thẳng cho Sếp duyệt =====
        if is_accounting_user:
            self.state = 'approved'  # 'Sếp Đang duyệt'
            _logger.info(">>> Proposal %s chuyển thẳng sang trạng thái 'approved' (Sếp đang duyệt) vì người gửi là Kế toán", self.name)
            now = fields.Datetime.now()
            self.date_proposal = now
            self.date_reviewed_accounting = now
            self.treasurer_confirmed = True

            partner_ids = self._get_approval_partners(
                include_manager=False,
                include_boss=True,          # gửi cho sếp
                include_accounting=False,   # không cần notify KT nữa
            )
            message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi trực tiếp cho Sếp duyệt bởi (Kế toán) <em>{self.env.user.name}</em>.</p>"
            self._send_notification(message, partner_ids)
            if self.director_user_id:
                self.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    user_id=self.director_user_id.id,
                    summary=f"Duyệt phiếu đề xuất {self.name}",
                    note=f"📌 Phiếu đề xuất <b>{self.name}</b> đang chờ duyệt.",
                    date_deadline=fields.Date.today() + timedelta(days=3),
                )
        # 3. Đổi trạng thái
        elif self.manager_id.user_id == self.env.user:
            self.state = 'reviewed_accounting'
            _logger.info(">>> Proposal %s chuyển sang trạng thái 'reviewed_accounting'", self.name)
            self.date_proposal = fields.Datetime.now()
            self.date_reviewed_manager = fields.Datetime.now()
            partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
            message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi <em>{self.env.user.name}</em>.</p>"
            self._send_notification(message, partner_ids)
        else:
            self.state = 'reviewed_manager'
            _logger.info(">>> Proposal %s chuyển sang trạng thái 'reviewed_manager'", self.name)
            self.date_proposal = fields.Datetime.now()
            partner_ids = self._get_approval_partners(include_manager=True, include_boss=False, include_accounting=False)
            message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi <em>{self.env.user.name}</em>.</p>"
            self._send_notification(message, partner_ids)
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
    def action_treasurer_comfirm(self):
        if self.state != 'reviewed_accounting':
            raise UserError("Chỉ phiếu đang xem xét mới được duyệt.")
        self.treasurer_confirmed = True
        treaserer_name = self.env.user.name
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được xác nhận bởi bởi <em>{treaserer_name}</em>.</p>"
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
        self._send_notification(message, partner_ids)
    def action_manager_approve(self):
        if self.state != 'reviewed_manager':
            raise UserError("Chỉ phiếu đang xem xét mới được duyệt.")
        self.state = 'reviewed_accounting'
        self.date_reviewed_manager = fields.Datetime.now()
        approver_name = self.env.user.name
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được xác nhận bởi <em>{approver_name}</em>.</p>"
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
        self._send_notification(message, partner_ids)


    def action_boss_approve(self):
        for record in self:
            if record.state != 'approved':
                raise UserError("Chỉ phiếu đang ở trạng thái đang kiểm tra mới được gửi kế toán.")
        self.state = 'waiting_accounting_paid'
        self.date_approved = fields.Datetime.now()
        # Gửi thông báo đến kế toán
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được duyệt bởi <em>{self.env.user.name}</em>.</p>"
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=True)
        self._send_notification(message, partner_ids)
        if self.director_user_id:
                self._close_activity(
                    user=self.director_user_id,
                    feedback="Đã duyệt"
                )
    def action_withdraw_submit(self):
        self.ensure_one()

        # ✅ Chỉ người tạo phiếu mới được rút lại
        if self.requested_by != self.env.user:
            raise UserError(_("Chỉ người đề xuất mới có quyền hủy gửi phiếu này."))

        # Xác định role của người tạo
        accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        is_accounting_user = bool(accounting_group and accounting_group in self.env.user.groups_id)
        is_manager_user = bool(self.manager_id and self.manager_id.user_id == self.env.user)

        # ===== RULE: 3 case được back =====
        # 1) NV thường -> đang chờ QL duyệt
        # 2) Trưởng phòng -> đang chờ KT duyệt
        # 3) Kế toán -> đang chờ Giám đốc duyệt
        if is_accounting_user:
            allowed_state = 'approved'
            waiting_label = "Giám đốc"
        elif is_manager_user:
            allowed_state = 'reviewed_accounting'
            waiting_label = "Kế toán"
        else:
            allowed_state = 'reviewed_manager'
            waiting_label = "Quản lý"

        if self.state != allowed_state:
            raise UserError(_(
                "Chỉ được hủy gửi khi phiếu đang chờ %s duyệt (đúng luồng gửi của bạn). "
                "Phiếu đã qua bước duyệt thì không thể rút lại."
            ) % waiting_label)

        old_state = self.state

        # ✅ Reset về nháp để sửa + reset các dấu duyệt
        reset_vals = {
            'state': 'draft',
            'treasurer_confirmed': False,
            'date_proposal': False,
            'date_reviewed_manager': False,
            'date_reviewed_accounting': False,
            'date_approved': False,
        }
        if self.type == 'material':
            reset_vals.update({
                'stock_check_done': False,
                'stock_checked_by': False,
                'stock_checked_date': False,
            })
        self.write(reset_vals)

        # ✅ Nếu đang ở bước Giám đốc (approved) thì thường có activity -> đóng lại
        if old_state == 'approved' and self.director_user_id:
            self._close_activity(
                user=self.director_user_id,
                feedback="Phiếu đã được rút lại để chỉnh sửa"
            )

        # Notify theo đúng “bên đang nhận”
        partner_ids = [self.requested_by.partner_id.id]

        if old_state == 'reviewed_manager':
            # đang chờ QL
            if self.manager_id and self.manager_id.user_id and self.manager_id.user_id.partner_id:
                partner_ids.append(self.manager_id.user_id.partner_id.id)

        elif old_state == 'reviewed_accounting':
            # đang chờ KT
            if accounting_group:
                for u in accounting_group.users:
                    if u.partner_id and u.partner_id.id not in partner_ids:
                        partner_ids.append(u.partner_id.id)

        elif old_state == 'approved':
            # đang chờ GĐ
            if self.director_user_id and self.director_user_id.partner_id:
                partner_ids.append(self.director_user_id.partner_id.id)

        message = (
            f"<p>Người đề xuất <em>{self.env.user.name}</em> đã <strong>hủy gửi</strong> "
            f"phiếu <strong>{self.name}</strong> để chỉnh sửa và sẽ gửi lại sau.</p>"
        )
        self._send_notification(message, partner_ids)

        return {'type': 'ir.actions.client', 'tag': 'reload'}
    def action_waiting_accounting_paid(self):
        if self.state != 'waiting_accounting_paid':
            raise UserError("Chỉ phiếu đã phê duyệt mới được hoàn tất.")
        # Chuyển sang trạng thái chờ kế toán chi tiền
        for record in self:
            payment_request = self.env['account.payment.request'].create({
                'proposal_sheet_id': record.id,
                'total': record.amount_total,
                'date': record.create_date,
                'project_id': record.project_id.id if record.project_id else None,
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
    def action_purchase_order(self):
        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.partner_id.id,
            'proposal_sheet_id': self.id,
            'date_order': self.create_date,
            'project_id': self.project_id.id,
            'user_id': self.env.user.id,
            'origin': f'{self._name} - {self.name}',
        })
        for line in self.material_line_ids:
            product = line.material_id.product_id
            self.env['purchase.order.line'].create({
                'order_id': purchase_order.id,
                'product_id': product.product_id.id,
                'product_uom': product.product_uom_id.id,
                'product_qty': product.quantity,
                'price_unit': product.price_unit,
                'tax_id': [(6, 0, [product.tax_id.id])],
                'account_analytic_id': line.account_analytic_id.id,
                'analytic_tag_ids': [(6, 0, line.analytic_tag_ids.ids)],
                'name': line.name,
            })
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được tạo thành phiếu mua hàng <strong>{purchase_order.name}</strong>.</p>"        
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=False, include_accounting=False)
        self._send_notification(message, partner_ids)
    def action_accounting_approve(self):
        if self.state != 'reviewed_accounting':
            raise UserError("Chỉ phiếu đã được Quản lý trình mới được Kế toán kiểm tra.")
        self.state = 'approved'
        self.date_reviewed_accounting = fields.Datetime.now()
        message = f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được kiểm tra bởi <em>{self.env.user.name}</em>.</p>"        
        partner_ids = self._get_approval_partners(include_manager=False, include_boss=True, include_accounting=False)
        # Gửi thông báo đến giám đốc
        self._send_notification(message, partner_ids)
        
        if self.director_user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.director_user_id.id,
                summary=f"Duyệt phiếu đề xuất {self.name}",
                note=f"📌 Phiếu đề xuất <b>{self.name}</b> đang chờ duyệt.",
                date_deadline=fields.Date.today() + timedelta(days=3),
            )
    def _close_activity(self, user, xmlid='mail.mail_activity_data_todo', feedback="Đã xử lý"):
            self.ensure_one()
            act_type = self.env.ref(xmlid)

            acts = self.env['mail.activity'].search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('activity_type_id', '=', act_type.id),
                ('user_id', '=', user.id),
                # ('state', '=', 'planned'),
            ])

            if acts:
                acts.action_feedback(feedback=feedback)
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
    def action_done(self):
        for rec in self:
            if rec.state not in ['approved', 'waiting_accounting_paid']:
                raise UserError("Không được phép hoàn tất phiếu này.")
            rec.state = 'done'            
            rec.message_post(body="Phiếu đề xuất đã hoàn tất.")

    @api.depends(
        'state',
        'type',
        'stock_check_done',
        'requested_by',
        'manager_id',
        'director_user_id',
        'treasurer_confirmed',
    )
    def _compute_show_buttons(self):
        current_user = self.env.user
        is_accounting_user = current_user.has_group('account.group_account_manager')

        for rec in self:
            is_creator = rec.requested_by.id == current_user.id
            is_manager = rec.manager_id.user_id.id == current_user.id if rec.manager_id and rec.manager_id.user_id else False
            is_boss = rec.director_user_id.id == current_user.id if rec.director_user_id else False

            can_stock_check = (
                rec.type == 'material'
                and rec.state == 'draft'
                and is_creator
            )

            rec.show_button_submit = rec.state == 'draft' and is_creator
            rec.show_button_manager_approve = rec.state == 'reviewed_manager' and is_manager
            rec.show_button_accounting_approve = (
                rec.state == 'reviewed_accounting'
                and is_accounting_user
                and rec.treasurer_confirmed
            )
            rec.show_button_boss_approve = rec.state == 'approved' and is_boss
            rec.show_button_waiting_accounting_paid = (
                rec.state == 'waiting_accounting_paid'
                and rec.type in ['expense', 'other']
                and is_accounting_user
            )
            rec.show_button_done = rec.state in ['approved', 'waiting_accounting_paid'] and is_accounting_user
            rec.show_button_reject = (
                (rec.state == 'reviewed_manager' and is_manager)
                or (rec.state == 'reviewed_accounting' and is_accounting_user)
                or (rec.state == 'approved' and is_boss)
            )
            rec.show_button_cancel = rec.state == 'draft' and is_creator
            rec.show_button_reset_draft = rec.state == 'rejected' and is_creator
            rec.show_button_withdraw_submit = (
                rec.state in ['reviewed_manager', 'reviewed_accounting', 'approved']
                and is_creator
            )

            # Nút xác nhận tồn thực tế: chỉ người đề xuất mới được bấm
            rec.show_button_apply_actual_stock = can_stock_check

            # Nút reset kiểm kho: chỉ người đề xuất mới được bấm sau khi đã xác nhận tồn
            rec.show_button_reset_stock_check = can_stock_check and rec.stock_check_done

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
            if not self.cost_estimate_line_id:
                raise ValidationError("Phiếu loại Vật tư bắt buộc phải chọn Hạng mục dự toán.")

            # Lấy tất cả dòng dự toán của task cho vật tư
            for material_line in self.cost_estimate_line_id.material_line_ids:
                material_lines.append((0, 0, {
                    'material_id': material_line.material_id.id,
                    'quantity': material_line.quantity,
                    'unit': material_line.unit.id,
                    'price_unit': material_line.price_unit or 0.0,
                    'vendor_id': material_line.vendor_id.id
                }))

            if not material_lines:
                raise ValidationError("Không tìm thấy chi tiết vật tư nào trong hạng mục dự toán này.")

            self.material_line_ids = material_lines
        elif self.type == 'expense':
            if not self.cost_estimate_line_id:
                raise ValidationError("Phiếu loại Chi phí bắt buộc phải chọn Hạng mục dự toán.")

            # Lấy trực tiếp các dòng chi phí từ hạng mục dự toán
            existing_expense_lines = self.cost_estimate_line_id.expense_line_ids
            if not existing_expense_lines:
                raise ValidationError("Không tìm thấy chi phí nào trong hạng mục dự toán này.")

            expense_lines = []
            for mapping in existing_expense_lines:
                expense_lines.append((0, 0, {
                    'expense_id': mapping.expense_id.id,   # Đã mapping sẵn
                    'quantity': mapping.quantity,          # Số lượng từ hạng mục
                    'unit': mapping.unit.id or mapping.expense_id.default_unit.id,
                    'price_unit': mapping.price_unit,
                    'type_expense': mapping.expense_id.type,
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
    @api.model
    def default_get(self, fields):
        res = super().default_get(fields)
        # Khi tạo mới → mặc định là ver mới
        res['is_new_proposal'] = True
        return res