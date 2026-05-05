from markupsafe import Markup
from odoo import models, fields, api, _
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

    department_id = fields.Many2one(
        'hr.department',
        string='Phòng Ban',
        required=True,
        default=lambda self: self.env.user.employee_id.department_id.id
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Người Quản Lý',
        compute='_compute_manager_id'
    )

    director_user_id = fields.Many2one(
        'res.users',
        string="Giám Đốc",
        default=lambda self: self._default_director_user(),
        readonly=True,
        copy=False
    )

    name = fields.Char(
        string='Mã Đề Xuất',
        default='New',
        readonly=True,
        copy=False
    )

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        tracking=True
    )

    task_id = fields.Many2one(
        'project.task',
        string='Nhiệm Vụ',
        tracking=True
    )

    requested_by = fields.Many2one(
        'res.users',
        string='Người Đề Xuất',
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        copy=False
    )

    treasurer_confirmed = fields.Boolean(
        string="Thủ quỹ đã xác nhận",
        default=False,
        copy=False
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    state = fields.Selection([
        ('draft', 'Nháp'),
        ('reviewed_manager', 'QL Đang trình'),
        ('reviewed_accounting', 'KTTH Đang kiểm tra'),
        ('approved', 'Sếp Đang duyệt'),
        ('waiting_accounting_paid', 'Chờ KT xử lý'),
        ('done', 'Hoàn tất'),
        ('rejected', 'Bị từ chối'),
        ('canceled', 'Đã hủy'),
    ], string="Trạng thái", default='draft', copy=False, tracking=True)

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Vị trí kho kiểm kê',
        domain="[('usage', '=', 'internal')]",
        default=lambda self: self._default_stock_location_id(),
        tracking=True,
    )

    stock_check_done = fields.Boolean(
        string='Đã xác nhận tồn thực tế',
        default=False,
        copy=False
    )

    stock_checked_by = fields.Many2one(
        'res.users',
        string='Người xác nhận tồn',
        copy=False,
        readonly=True
    )

    stock_checked_date = fields.Datetime(
        string='Ngày xác nhận tồn',
        copy=False,
        readonly=True
    )

    cost_additional_expense_line_id = fields.Many2one(
        'cost.additional.expense.line',
        string='Dòng chi phí bổ sung',
        domain="[('project_id', '=', project_id)]",
        help="Chọn dòng chi phí bổ sung liên quan đến dự án này."
    )

    date_proposal = fields.Date(
        string='Ngày Đề Xuất',
        copy=False
    )

    date_reviewed_manager = fields.Date(
        string='Ngày QL duyệt',
        copy=False
    )

    date_reviewed_accounting = fields.Date(
        string='Ngày KTTH kiểm tra',
        copy=False
    )

    date_approved = fields.Date(
        string='Ngày Sếp duyệt',
        copy=False
    )

    type = fields.Selection([
        ('material', 'Vật Tư'),
        ('expense', 'Chi Phí Công Trình'),
        ('other', 'Chi phí Khác'),
    ], required=True, string='Loại Đề Xuất', default='material', tracking=True)

    material_line_ids = fields.One2many(
        'proposal.material.line',
        'sheet_id',
        string='Chi Tiết Vật Tư',
        domain=[('type', '=', 'material')],
        copy=True
    )

    expense_line_ids = fields.One2many(
        'proposal.expense.line',
        'sheet_id',
        string='Chi Tiết Chi Phí Công Trình',
        domain=[('type', '=', 'expense')],
        copy=True
    )

    expense_noproject_line_ids = fields.One2many(
        'proposal.other.expense.line',
        'sheet_id',
        string='Chi Tiết Khác',
        domain=[('type', '=', 'other')],
        order='sequence, id',
        copy=True
    )

    amount_total = fields.Float(
        string='Tổng Thành Tiền',
        compute='_compute_amount_total',
        store=True
    )

    amount_total_taxes = fields.Float(
        string='Tổng Thành Tiền (Có Thuế)',
        compute='_compute_amount_total_taxes',
        store=True
    )

    take_note = fields.Text(
        string='Ghi Chú',
        tracking=True
    )

    treasurer_confirmed_note = fields.Char(
        compute='_compute_treasurer_confirmed_note',
        store=False
    )

    is_new_proposal = fields.Boolean(
        string="Ver mới",
        default=True,
        copy=False,
        help="Dòng mới dùng product_id. Các dòng cũ tạo trước khi nâng cấp sẽ không được tick và vẫn hiển thị material_id."
    )

    contract_num = fields.Char(
        string="Số hợp đồng",
        related="project_id.num_contract",
        store=True,
        readonly=True,
    )

    show_button_submit = fields.Boolean(compute='_compute_show_buttons')
    show_button_manager_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_accounting_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_boss_approve = fields.Boolean(compute='_compute_show_buttons')
    show_button_waiting_accounting_paid = fields.Boolean(compute='_compute_show_buttons')
    show_button_done = fields.Boolean(compute='_compute_show_buttons')
    show_button_reject = fields.Boolean(compute='_compute_show_buttons')
    show_button_cancel = fields.Boolean(compute='_compute_show_buttons')
    show_button_reset_draft = fields.Boolean(compute='_compute_show_buttons')
    show_button_withdraw_submit = fields.Boolean(compute='_compute_show_buttons')
    show_button_apply_actual_stock = fields.Boolean(compute='_compute_show_buttons')
    show_button_reset_stock_check = fields.Boolean(compute='_compute_show_buttons')

    is_type_readonly = fields.Boolean(
        compute='_compute_is_type_readonly',
        store=False
    )

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

    approver_boss_id = fields.Many2one(
        'res.users',
        string="Người Duyệt Cuối",
        default=lambda self: self.env['hr.department'].get_manager_id_by_name('Administration').user_id.id
        if self.env['hr.department'].get_manager_id_by_name('Administration') else False,
        readonly=True,
        copy=False
    )

    # =========================
    # DEFAULT
    # =========================

    @api.model
    def _default_stock_location_id(self):
        location = self.env['stock.location'].search([
            ('usage', '=', 'internal'),
            '|',
            ('complete_name', 'ilike', 'Nguyên vật liệu'),
            ('name', 'ilike', 'Nguyên vật liệu')
        ], limit=1)

        if not location:
            location = self.env['stock.location'].search([
                ('usage', '=', 'internal')
            ], limit=1)

        return location.id if location else False

    @api.model
    def _default_director_user(self):
        group = self.env.ref(
            'custom_director_role.group_director',
            raise_if_not_found=False
        )
        if not group:
            return False

        user = self.env['res.users'].search([
            ('groups_id', 'in', group.id)
        ], limit=1)

        return user.id if user else False

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        res['is_new_proposal'] = True

        task_id = self.env.context.get('default_task_id')
        if task_id:
            task = self.env['project.task'].browse(task_id)
            if task.exists():
                res['task_id'] = task.id
                res['project_id'] = task.project_id.id

        return res

    # =========================
    # COMPUTE
    # =========================

    @api.depends('department_id')
    def _compute_manager_id(self):
        for record in self:
            record.manager_id = record.department_id.manager_id if record.department_id else False

    @api.depends('treasurer_confirmed')
    def _compute_treasurer_confirmed_note(self):
        for rec in self:
            rec.treasurer_confirmed_note = "Thủ quỹ đã xác nhận" if rec.treasurer_confirmed else ""

    @api.depends(
        'type',
        'material_line_ids.price_total',
        'expense_line_ids.price_total',
        'expense_noproject_line_ids.amount'
    )
    def _compute_amount_total(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total = sum(sheet.material_line_ids.mapped('price_total'))
            elif sheet.type == 'expense':
                sheet.amount_total = sum(sheet.expense_line_ids.mapped('price_total'))
            elif sheet.type == 'other':
                sheet.amount_total = sum(sheet.expense_noproject_line_ids.mapped('amount'))
            else:
                sheet.amount_total = 0.0

    @api.depends(
        'type',
        'material_line_ids.price_total_taxed',
        'expense_line_ids.price_total',
        'expense_noproject_line_ids.amount_total',
    )
    def _compute_amount_total_taxes(self):
        for sheet in self:
            if sheet.type == 'material':
                sheet.amount_total_taxes = sum(sheet.material_line_ids.mapped('price_total_taxed'))
            elif sheet.type == 'expense':
                sheet.amount_total_taxes = sheet.amount_total or 0.0
            elif sheet.type == 'other':
                sheet.amount_total_taxes = sum(sheet.expense_noproject_line_ids.mapped('amount_total'))
            else:
                sheet.amount_total_taxes = 0.0

    @api.depends(
        'state',
        'type',
        'stock_check_done',
        'requested_by',
        'manager_id',
        'director_user_id',
        'treasurer_confirmed',
        'material_line_ids.count_diff_qty',
    )
    def _compute_show_buttons(self):
        current_user = self.env.user
        is_accounting_user = current_user.has_group('account.group_account_manager')

        for rec in self:
            is_creator = rec.requested_by.id == current_user.id
            is_manager = (
                rec.manager_id
                and rec.manager_id.user_id
                and rec.manager_id.user_id.id == current_user.id
            )
            is_boss = (
                rec.director_user_id
                and rec.director_user_id.id == current_user.id
            )

            stock_check_lines = rec._get_stock_check_lines()
            has_stock_diff = any(bool(line.count_diff_qty) for line in stock_check_lines)

            can_stock_check = (
                rec.state == 'draft'
                and is_creator
                and has_stock_diff
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

            rec.show_button_done = (
                rec.state in ['approved', 'waiting_accounting_paid']
                and is_accounting_user
            )

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

            rec.show_button_apply_actual_stock = can_stock_check
            rec.show_button_reset_stock_check = can_stock_check and rec.stock_check_done

    @api.depends('material_line_ids', 'expense_line_ids', 'expense_noproject_line_ids')
    def _compute_is_type_readonly(self):
        for rec in self:
            rec.is_type_readonly = bool(
                rec.material_line_ids
                or rec.expense_line_ids
                or rec.expense_noproject_line_ids
            )

    # =========================
    # CREATE / COPY / WRITE / DELETE
    # =========================

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalSheet with vals: %s", vals)

        if not vals.get('type'):
            if vals.get('material_line_ids'):
                vals['type'] = 'material'
            elif vals.get('expense_line_ids'):
                vals['type'] = 'expense'
            elif vals.get('expense_noproject_line_ids'):
                vals['type'] = 'other'
            else:
                raise ValidationError('Vui lòng chọn loại đề xuất trước khi lưu.')

        vals['is_new_proposal'] = True

        task = False
        ctx_task_id = self.env.context.get('default_task_id')

        if not vals.get('task_id') and ctx_task_id:
            task = self.env['project.task'].browse(ctx_task_id)
            if task.exists():
                vals['task_id'] = task.id

        if not vals.get('project_id') and vals.get('task_id'):
            task = task or self.env['project.task'].browse(vals['task_id'])
            if task.exists() and task.project_id:
                vals['project_id'] = task.project_id.id

        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('proposal.sheet') or 'New'

        return super().create(vals)

    def copy(self, default=None):
        self.ensure_one()
        default = dict(default or {})

        default.update({
            # Mã mới
            'name': self.env['ir.sequence'].next_by_code('proposal.sheet') or 'New',

            # Bản sao luôn quay về nháp
            'state': 'draft',

            # Người sao chép là người đề xuất mới
            'requested_by': self.env.user.id,

            # Reset duyệt
            'treasurer_confirmed': False,
            'date_proposal': False,
            'date_reviewed_manager': False,
            'date_reviewed_accounting': False,
            'date_approved': False,

            # Reset xác nhận tồn thực tế
            'stock_check_done': False,
            'stock_checked_by': False,
            'stock_checked_date': False,

            # Luôn là form/dòng kiểu mới
            'is_new_proposal': True,
        })

        new_record = super(ProposalSheet, self).copy(default)

        # Reset lại kiểm kho trên dòng vật tư theo tồn hiện tại
        if new_record.type == 'material' and new_record.material_line_ids:
            for line in new_record.material_line_ids:
                product = line.product_id

                # Nếu dòng cũ dùng material_id thì cố lấy product từ material_id
                if not product and line.material_id and hasattr(line.material_id, 'product_id'):
                    product = line.material_id.product_id

                current_stock_qty = 0.0

                if product and new_record.stock_location_id:
                    # Lấy tồn hiện tại theo đúng vị trí kho của phiếu
                    current_stock_qty = product.with_context(
                        location=new_record.stock_location_id.id
                    ).qty_available

                vals_line = {}

                # SL kiểm kho = tồn hiện tại để chênh lệch ban đầu = 0
                if 'actual_count_qty' in line._fields:
                    vals_line['actual_count_qty'] = current_stock_qty

                # Reset ghi chú kiểm kho
                if 'count_note' in line._fields:
                    vals_line['count_note'] = False

                # Reset dữ liệu đã xác nhận lần trước
                if 'last_counted_qty' in line._fields:
                    vals_line['last_counted_qty'] = 0.0

                if 'last_counted_by' in line._fields:
                    vals_line['last_counted_by'] = False

                if 'last_counted_date' in line._fields:
                    vals_line['last_counted_date'] = False

                # Nếu count_diff_qty là field thường thì set 0.
                # Nếu là computed field thì Odoo sẽ tự tính lại.
                if 'count_diff_qty' in line._fields and not line._fields['count_diff_qty'].compute:
                    vals_line['count_diff_qty'] = 0.0

                if vals_line:
                    line.write(vals_line)

        new_record.message_post(
            body=Markup(
                f"Phiếu này được sao chép từ phiếu <strong>{self.name}</strong> "
                f"bởi <em>{self.env.user.name}</em>."
            )
        )

        return new_record

    def write(self, vals):
        for rec in self:
            if 'type' in vals and vals['type'] != rec.type:
                if rec.material_line_ids or rec.expense_line_ids or rec.expense_noproject_line_ids:
                    raise ValidationError(
                        "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí."
                    )

        return super(ProposalSheet, self).write(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ('draft', 'canceled', 'rejected'):
                raise UserError(
                    "Chỉ có thể xóa khi phiếu ở trạng thái 'Nháp', 'Đã hủy' hoặc 'Từ chối'."
                )
        return super().unlink()

    # =========================
    # CONSTRAINT / ONCHANGE
    # =========================

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

    @api.onchange('type')
    def _onchange_type(self):
        if self.material_line_ids or self.expense_line_ids or self.expense_noproject_line_ids:
            raise ValidationError(
                "Không thể thay đổi loại đề xuất khi đã có dòng vật tư hoặc chi phí. "
                "Vui lòng xóa các dòng hiện có trước khi thay đổi."
            )

    @api.onchange('task_id')
    def _onchange_task_id(self):
        if self.task_id and not self.project_id:
            self.project_id = self.task_id.project_id.id

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if not self.env.context.get('from_task'):
            self.task_id = False

        return {
            'domain': {
                'task_id': [('project_id', '=', self.project_id.id)]
            }
        }

    @api.onchange('material_line_ids', 'material_line_ids.cost_estimate_line_id')
    def _onchange_cost_estimate_line_ids(self):
        for sheet in self:
            old_auto_ids = set(sheet.auto_cost_estimate_line_ids.ids)
            current_header_ids = set(sheet.cost_estimate_line_ids.ids)
            new_auto_ids = set(sheet.material_line_ids.mapped('cost_estimate_line_id').ids)

            manual_ids = current_header_ids - old_auto_ids
            final_ids = manual_ids | new_auto_ids

            sheet.auto_cost_estimate_line_ids = [(6, 0, list(new_auto_ids))]
            sheet.cost_estimate_line_ids = [(6, 0, list(final_ids))]

    # =========================
    # NOTIFICATION
    # =========================

    def _send_notification(self, message, partner_ids=None):
        self.ensure_one()

        partner_ids = partner_ids or []
        partner_ids = [pid for pid in partner_ids if pid]

        for rec in self:
            rec.message_follower_ids.sudo().unlink()

        existing_followers = self.message_partner_ids.ids
        new_partners = [pid for pid in partner_ids if pid not in existing_followers]

        if new_partners:
            self.message_subscribe(partner_ids=new_partners)

        self.message_post(
            body=Markup(message),
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
            partner_ids=partner_ids
        )

    def _get_approval_partners(self, include_manager, include_boss, include_accounting):
        self.ensure_one()

        partner_ids = []

        if self.requested_by and self.requested_by.partner_id:
            partner_ids.append(self.requested_by.partner_id.id)

        if include_manager and self.department_id and self.manager_id and self.manager_id.user_id:
            partner = self.manager_id.user_id.partner_id
            if partner and partner.id not in partner_ids:
                partner_ids.append(partner.id)

        if include_boss and self.director_user_id:
            partner = self.director_user_id.partner_id
            if partner and partner.id not in partner_ids:
                partner_ids.append(partner.id)

        if include_accounting:
            accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
            if accounting_group:
                for user in accounting_group.users:
                    if user.partner_id and user.partner_id.id not in partner_ids:
                        partner_ids.append(user.partner_id.id)

        return partner_ids

    def _close_activity(self, user, xmlid='mail.mail_activity_data_todo', feedback="Đã xử lý"):
        self.ensure_one()

        if not user:
            return

        act_type = self.env.ref(xmlid, raise_if_not_found=False)
        if not act_type:
            return

        acts = self.env['mail.activity'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('activity_type_id', '=', act_type.id),
            ('user_id', '=', user.id),
        ])

        if acts:
            acts.action_feedback(feedback=feedback)

    # =========================
    # STOCK CHECK
    # =========================

    def _get_stock_check_lines(self):
        self.ensure_one()

        if self.type == 'material':
            return self.material_line_ids

        return self.env['proposal.material.line']

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
                    raise UserError(
                        f"Dòng vật tư '{line.display_name}' chưa có sản phẩm nên không thể cập nhật tồn."
                    )

                if line.actual_count_qty < 0:
                    raise UserError(
                        f"Số lượng kiểm kê thực tế của sản phẩm '{line.product_id.display_name}' không được âm."
                    )

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

                quant.with_context(from_proposal_sheet_actual_stock=True).sudo().action_apply_inventory()

                line.write({
                    'last_counted_qty': target_qty,
                    'last_counted_by': self.env.user.id,
                    'last_counted_date': fields.Datetime.now(),
                })

                log_items.append(
                    f"<li><b>{line.product_id.display_name}</b>: "
                    f"hệ thống {old_qty:g} → thực tế {target_qty:g} "
                    f"(chênh {(target_qty - old_qty):g})</li>"
                )

            rec.sudo().write({
                'stock_check_done': True,
                'stock_checked_by': self.env.user.id,
                'stock_checked_date': fields.Datetime.now(),
            })

            message = (
                f"<p>Đã xác nhận tồn thực tế cho phiếu <strong>{rec.name}</strong> tại kho "
                f"<strong>{rec.stock_location_id.display_name}</strong> bởi "
                f"<em>{self.env.user.name}</em>.</p>"
                f"<ul>{''.join(log_items)}</ul>"
            )

            rec.message_post(body=Markup(message))

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

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

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    # =========================
    # WORKFLOW ACTIONS
    # =========================

    def action_submit(self):
        self.ensure_one()

        if self.type == 'material' and not self.material_line_ids:
            raise ValidationError(_("Phiếu đề xuất vật tư phải có ít nhất một dòng vật tư trước khi gửi duyệt."))

        if self.type == 'expense' and not self.expense_line_ids:
            raise ValidationError(_("Phiếu đề xuất chi phí phải có ít nhất một dòng chi phí trước khi gửi duyệt."))

        if self.type == 'other' and not self.expense_noproject_line_ids:
            raise ValidationError(_("Phiếu chi phí khác phải có ít nhất một dòng trước khi gửi duyệt."))

        if self.state != 'draft':
            raise UserError(_("Chỉ phiếu ở trạng thái nháp mới được gửi duyệt."))

        if self.type == 'material' and not self.stock_check_done:
            has_stock_diff = any(bool(line.count_diff_qty) for line in self.material_line_ids)
            if has_stock_diff:
                raise ValidationError(_("Phiếu vật tư phải được xác nhận tồn thực tế trước khi gửi duyệt."))

        accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        is_accounting_user = accounting_group and accounting_group in self.env.user.groups_id

        if is_accounting_user:
            self.state = 'approved'
            now = fields.Date.today()
            self.date_proposal = now
            self.date_reviewed_accounting = now
            self.treasurer_confirmed = True

            partner_ids = self._get_approval_partners(
                include_manager=False,
                include_boss=True,
                include_accounting=False,
            )

            message = (
                f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi trực tiếp "
                f"cho Sếp duyệt bởi Kế toán <em>{self.env.user.name}</em>.</p>"
            )

            self._send_notification(message, partner_ids)

            if self.director_user_id:
                self.activity_schedule(
                    activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                    user_id=self.director_user_id.id,
                    summary=f"Duyệt phiếu đề xuất {self.name}",
                    note=f"📌 Phiếu đề xuất <b>{self.name}</b> đang chờ duyệt.",
                    date_deadline=fields.Date.today() + timedelta(days=3),
                )

        elif self.manager_id.user_id == self.env.user:
            self.state = 'reviewed_accounting'
            self.date_proposal = fields.Date.today()
            self.date_reviewed_manager = fields.Date.today()

            partner_ids = self._get_approval_partners(
                include_manager=False,
                include_boss=False,
                include_accounting=True
            )

            message = (
                f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi "
                f"<em>{self.env.user.name}</em>.</p>"
            )

            self._send_notification(message, partner_ids)

        else:
            self.state = 'reviewed_manager'
            self.date_proposal = fields.Date.today()

            partner_ids = self._get_approval_partners(
                include_manager=True,
                include_boss=False,
                include_accounting=False
            )

            message = (
                f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được gửi duyệt bởi "
                f"<em>{self.env.user.name}</em>.</p>"
            )

            self._send_notification(message, partner_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_treasurer_comfirm(self):
        self.ensure_one()

        if self.state != 'reviewed_accounting':
            raise UserError("Chỉ phiếu đang xem xét mới được duyệt.")

        self.treasurer_confirmed = True

        message = (
            f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được xác nhận bởi "
            f"<em>{self.env.user.name}</em>.</p>"
        )

        partner_ids = self._get_approval_partners(
            include_manager=False,
            include_boss=False,
            include_accounting=True
        )

        self._send_notification(message, partner_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_manager_approve(self):
        self.ensure_one()

        if self.state != 'reviewed_manager':
            raise UserError("Chỉ phiếu đang xem xét mới được duyệt.")

        self.state = 'reviewed_accounting'
        self.date_reviewed_manager = fields.Date.today()

        message = (
            f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được xác nhận bởi "
            f"<em>{self.env.user.name}</em>.</p>"
        )

        partner_ids = self._get_approval_partners(
            include_manager=False,
            include_boss=False,
            include_accounting=True
        )

        self._send_notification(message, partner_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_accounting_approve(self):
        self.ensure_one()

        if self.state != 'reviewed_accounting':
            raise UserError("Chỉ phiếu đã được Quản lý trình mới được Kế toán kiểm tra.")

        self.state = 'approved'
        self.date_reviewed_accounting = fields.Date.today()

        message = (
            f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được kiểm tra bởi "
            f"<em>{self.env.user.name}</em>.</p>"
        )

        partner_ids = self._get_approval_partners(
            include_manager=False,
            include_boss=True,
            include_accounting=False
        )

        self._send_notification(message, partner_ids)

        if self.director_user_id:
            self.activity_schedule(
                activity_type_id=self.env.ref('mail.mail_activity_data_todo').id,
                user_id=self.director_user_id.id,
                summary=f"Duyệt phiếu đề xuất {self.name}",
                note=f"📌 Phiếu đề xuất <b>{self.name}</b> đang chờ duyệt.",
                date_deadline=fields.Date.today() + timedelta(days=3),
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_boss_approve(self):
        self.ensure_one()

        if self.state != 'approved':
            raise UserError("Chỉ phiếu đang ở trạng thái Sếp đang duyệt mới được duyệt.")

        self.state = 'waiting_accounting_paid'
        self.date_approved = fields.Date.today()

        message = (
            f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được duyệt bởi "
            f"<em>{self.env.user.name}</em>.</p>"
        )

        partner_ids = self._get_approval_partners(
            include_manager=False,
            include_boss=False,
            include_accounting=True
        )

        self._send_notification(message, partner_ids)

        if self.director_user_id:
            self._close_activity(
                user=self.director_user_id,
                feedback="Đã duyệt"
            )

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_withdraw_submit(self):
        self.ensure_one()

        if self.requested_by != self.env.user:
            raise UserError(_("Chỉ người đề xuất mới có quyền hủy gửi phiếu này."))

        accounting_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
        is_accounting_user = bool(accounting_group and accounting_group in self.env.user.groups_id)
        is_manager_user = bool(self.manager_id and self.manager_id.user_id == self.env.user)

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
                "Chỉ được hủy gửi khi phiếu đang chờ %s duyệt đúng luồng gửi của bạn. "
                "Phiếu đã qua bước duyệt thì không thể rút lại."
            ) % waiting_label)

        old_state = self.state

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

        if old_state == 'approved' and self.director_user_id:
            self._close_activity(
                user=self.director_user_id,
                feedback="Phiếu đã được rút lại để chỉnh sửa"
            )

        partner_ids = []

        if self.requested_by and self.requested_by.partner_id:
            partner_ids.append(self.requested_by.partner_id.id)

        if old_state == 'reviewed_manager':
            if self.manager_id and self.manager_id.user_id and self.manager_id.user_id.partner_id:
                partner_ids.append(self.manager_id.user_id.partner_id.id)

        elif old_state == 'reviewed_accounting':
            if accounting_group:
                for user in accounting_group.users:
                    if user.partner_id and user.partner_id.id not in partner_ids:
                        partner_ids.append(user.partner_id.id)

        elif old_state == 'approved':
            if self.director_user_id and self.director_user_id.partner_id:
                partner_ids.append(self.director_user_id.partner_id.id)

        message = (
            f"<p>Người đề xuất <em>{self.env.user.name}</em> đã <strong>hủy gửi</strong> "
            f"phiếu <strong>{self.name}</strong> để chỉnh sửa và sẽ gửi lại sau.</p>"
        )

        self._send_notification(message, partner_ids)

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_waiting_accounting_paid(self):
        self.ensure_one()

        if self.state != 'waiting_accounting_paid':
            raise UserError("Chỉ phiếu đã phê duyệt mới được chi tiền.")

        payment_request = self.env['account.payment.request'].create({
            'proposal_sheet_id': self.id,
            'total': self.amount_total,
            'date': self.create_date,
            'project_id': self.project_id.id if self.project_id else False,
            'proposal_person_id': self.requested_by.id,
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Payment Request',
            'res_model': 'account.payment.request',
            'view_mode': 'form',
            'res_id': payment_request.id,
            'target': 'current',
        }

    def action_done(self):
        for rec in self:
            if rec.state not in ['approved', 'waiting_accounting_paid']:
                raise UserError("Không được phép hoàn tất phiếu này.")

            rec.state = 'done'
            rec.message_post(body="Phiếu đề xuất đã hoàn tất.")

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_cancel(self):
        for rec in self:
            if rec.state in ['done', 'canceled']:
                raise UserError("Không thể hủy phiếu đã hoàn tất hoặc đã hủy.")

            rec.state = 'canceled'
            rec.message_post(body="Phiếu đã được hủy.")

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    def action_reset_to_draft(self):
        self.ensure_one()

        if self.state != 'rejected':
            raise UserError("Chỉ phiếu bị từ chối mới được reset về nháp.")

        self.write({
            'state': 'draft',
            'treasurer_confirmed': False,
            'date_proposal': False,
            'date_reviewed_manager': False,
            'date_reviewed_accounting': False,
            'date_approved': False,
        })

        self.message_post(body="Phiếu được reset về Nháp.")

        return {
            'type': 'ir.actions.client',
            'tag': 'reload'
        }

    # =========================
    # PURCHASE / PDF / ESTIMATE
    # =========================

    def action_purchase_order(self):
        self.ensure_one()

        if not hasattr(self, 'partner_id') or not self.partner_id:
            raise UserError("Phiếu chưa có nhà cung cấp/đối tác để tạo đơn mua hàng.")

        purchase_order = self.env['purchase.order'].create({
            'partner_id': self.partner_id.id,
            'proposal_sheet_id': self.id,
            'date_order': self.create_date,
            'project_id': self.project_id.id if self.project_id else False,
            'user_id': self.env.user.id,
            'origin': f'{self._name} - {self.name}',
        })

        for line in self.material_line_ids:
            product = line.material_id.product_id if line.material_id else line.product_id

            if not product:
                continue

            self.env['purchase.order.line'].create({
                'order_id': purchase_order.id,
                'product_id': product.id,
                'product_uom': line.unit.id if line.unit else product.uom_po_id.id,
                'product_qty': line.quantity,
                'price_unit': line.price_unit,
                'tax_id': [(6, 0, line.tax_id.ids)] if line.tax_id else False,
                'name': line.description or product.display_name,
            })

        message = (
            f"<p>Phiếu đề xuất <strong>{self.name}</strong> đã được tạo thành "
            f"phiếu mua hàng <strong>{purchase_order.name}</strong>.</p>"
        )

        partner_ids = self._get_approval_partners(
            include_manager=False,
            include_boss=False,
            include_accounting=False
        )

        self._send_notification(message, partner_ids)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Đơn mua hàng',
            'res_model': 'purchase.order',
            'view_mode': 'form',
            'res_id': purchase_order.id,
            'target': 'current',
        }

    def action_load_from_estimate(self):
        self.ensure_one()

        if not self.type:
            raise ValidationError("Vui lòng chọn Loại đề xuất trước khi tải dữ liệu.")

        if not hasattr(self, 'cost_estimate_line_id') or not self.cost_estimate_line_id:
            raise ValidationError("Chức năng này đang dùng cost_estimate_line_id nhưng model hiện tại chưa khai báo field này.")

        self.material_line_ids = [(5, 0, 0)]
        self.expense_line_ids = [(5, 0, 0)]

        material_lines = []
        expense_lines = []

        if self.type == 'material':
            for material_line in self.cost_estimate_line_id.material_line_ids:
                material_lines.append((0, 0, {
                    'material_id': material_line.material_id.id,
                    'quantity': material_line.quantity,
                    'unit': material_line.unit.id,
                    'price_unit': material_line.price_unit or 0.0,
                    'vendor_id': material_line.vendor_id.id,
                }))

            if not material_lines:
                raise ValidationError("Không tìm thấy chi tiết vật tư nào trong hạng mục dự toán này.")

            self.material_line_ids = material_lines

        elif self.type == 'expense':
            existing_expense_lines = self.cost_estimate_line_id.expense_line_ids

            if not existing_expense_lines:
                raise ValidationError("Không tìm thấy chi phí nào trong hạng mục dự toán này.")

            for mapping in existing_expense_lines:
                expense_lines.append((0, 0, {
                    'expense_id': mapping.expense_id.id,
                    'quantity': mapping.quantity,
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

    # =========================
    # VIEW CUSTOM
    # =========================

    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super().fields_view_get(
            view_id=view_id,
            view_type=view_type,
            toolbar=toolbar,
            submenu=submenu
        )

        return res