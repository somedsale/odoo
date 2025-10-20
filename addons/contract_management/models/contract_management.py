# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from markupsafe import Markup, escape
import re

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    contract_id = fields.Many2one('contract.management', string='Contract', readonly=True)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.contract_id:
                contract_vals = {
                    'name': f'Hợp đồng cho đơn hàng {order.name}',
                    'sale_order_id': order.id,
                    'partner_id': order.partner_id.id,
                    'stage': 'negotiating',
                    'company_id': order.company_id.id,
                }
                contract = self.env['contract.management'].create(contract_vals)
                order.contract_id = contract.id
        return res


class ContractManagement(models.Model):
    _name = 'contract.management'
    _description = 'Contract Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    name = fields.Char(string='Tên hợp đồng', required=True, tracking=True)
    num_contract = fields.Char(string='Số hợp đồng')
    contract_value = fields.Float(string='Giá trị hợp đồng')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True, tracking=True)
    date_execution = fields.Date(string='Ngày thực hiện')
    date_completion = fields.Date(string='Ngày hoàn thành')
    # ❗️ĐÃ BỎ 'preparing'
    stage = fields.Selection([
        ('negotiating', 'Đang thương thảo hợp đồng'),
        ('executing', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('canceled', 'Đã hủy'),
    ], string='Giai đoạn', default='negotiating', required=True, tracking=True)

    project_id = fields.Many2one('project.project', string='Dự án', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    signature_date = fields.Date(string='Ngày ký hợp đồng')
    planned_start_date = fields.Date(string='Ngày bắt đầu')
    planned_end_date = fields.Date(string='Ngày kết thúc')
    description = fields.Text(string='Mô tả')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu')
    warranty_time = fields.Integer(string="Thời gian bảo hành (tháng)")
    # ---------- Computed Fields ----------


    # ---------- Helpers ----------
    def _ensure_from_stage(self, allowed_stages):
        """Đảm bảo record đang ở 1 trong các stage cho phép."""
        for rec in self:
            if rec.stage not in allowed_stages:
                raise UserError(_(f"Không thể chuyển giai đoạn từ trạng thái '{rec.stage}'."))
        return True

    def _collect_task_stages(self):
        """Lấy các project.task.type theo bộ ref đã chuẩn hóa."""
        refs = [
            'contract_management.task_type_new_order',
            'contract_management.task_type_purchase',
            'contract_management.task_type_production',
            'contract_management.task_type_delivery',
            'contract_management.task_type_installation',
            'contract_management.task_type_acceptance',
            'contract_management.task_type_completed',
        ]
        task_stages = self.env['project.task.type']
        missing = []
        for r in refs:
            try:
                stage = self.env.ref(r)
                task_stages |= stage
            except ValueError:
                missing.append(r)
        if missing:
            raise UserError(_("Thiếu cấu hình cột trạng thái công việc: %s") % ", ".join(missing))
        return task_stages

    def _prepare_project_vals(self):
        """Chuẩn bị dữ liệu tạo Project từ hợp đồng (khi vào executing)."""
        self.ensure_one()
        # Đặt tên dự án
        if self.sale_order_id.x_project_name:
            name_project = f"Số HĐ {self.num_contract or '...'} - {self.sale_order_id.x_project_name}"
        else:
            name_project = self.sale_order_id.name

        task_stages = self._collect_task_stages()

        vals = {
            'name': name_project,
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'contract_id': self.id,
            'type_ids': [(6, 0, task_stages.ids)],
            'allow_timesheets': False,
            'allow_billable': False,
            'date_start': self.planned_start_date,
            'date': self.planned_end_date,
            'description': self.description,
        }

        # Gán PM nếu có
        manager_id = self.env['hr.department'].get_manager_id_by_name('Kế hoạch - Sản xuất')
        if manager_id:
            vals['user_id'] = manager_id.user_id.id
            _logger.info("Project Manager assigned: %s", manager_id)
        else:
            _logger.info("No Project Manager assigned")

        return vals

    def _create_project_and_sync(self):
        """Tạo Project, liên kết và copy đính kèm."""
        self.ensure_one()
        if self.project_id:
            return self.project_id

        project = self.env['project.project'].sudo().create(self._prepare_project_vals())
        self.sudo().project_id = project

        # Đồng bộ tài liệu
        if self.attachment_ids:
            for att in self.sudo().attachment_ids:
                att.sudo().copy({'res_model': 'project.project', 'res_id': project.id})

        return project

    def _create_cost_estimate_if_needed(self, project):
        """Tạo Dự toán từ SO nếu chưa có."""
        self.ensure_one()
        so = self.sale_order_id
        if so.cost_estimate_id:
            return so.cost_estimate_id

        # Chuẩn bị dòng dự toán từ các dòng SO
        line_vals = []
        for line in so.order_line:
            if line.product_id:
                line_vals.append((0, 0, {
                    'product_id': line.product_id.id,
                    'unit': line.product_uom.id,
                    'quantity': line.product_uom_qty,
                    'sale_order_line_id': line.id,
                }))

        budget_vals = {
            'name': f'Dự toán cho {project.name}',
            'sale_order_id': so.id,
            'project_id': project.id,
            'line_ids': line_vals,
        }
        ce = self.env['cost.estimate'].create(budget_vals)
        so.cost_estimate_id = ce.id
        return ce

    # ---------- Actions (đã bỏ preparing) ----------
    def action_to_executing(self):
        """Thương thảo → Thực hiện (tạo Project, Customer Contract, copy tài liệu, tạo Dự toán nếu cần)."""
        self._ensure_from_stage(['negotiating'])
        self.date_execution = fields.Datetime.now()

        for rec in self:
            rec.stage = 'executing'

            # 🔹 1. Tạo Project nếu chưa có
            project = rec._create_project_and_sync()

            # 🔹 2. Tạo Customer Contract nếu chưa có
            existing_customer_contract = self.env['customer.contract'].search([
                ('management_id', '=', rec.id)
            ], limit=1)

            if not existing_customer_contract:
                customer_contract_vals = {
                    'contract_number': rec.num_contract or '/',
                    'partner_id': rec.partner_id.id,
                    'project_id': project.id if project else False,
                    'amount_total': rec.contract_value or 0.0,
                    'currency_id': rec.env.company.currency_id.id,
                    'warranty_time': rec.warranty_time or 0.0,
                    'management_id': rec.id,
                    'date': rec.signature_date or fields.Date.today(),
                }

                customer_contract = self.env['customer.contract'].sudo().create(customer_contract_vals)
                _logger.info(f"✅ Created Customer Contract {customer_contract.name} for Contract Management {rec.name}")

                # Đăng message thông báo
                rec.message_post(
                    body=Markup(
                        f"📄 Đã tự động tạo **Hợp đồng khách hàng** "
                        f"<a href='/web#id={customer_contract.id}&model=customer.contract&view_type=form' target='_blank'>{customer_contract.display_name}</a>."
                    )
                )
            else:
                _logger.info(f"ℹ️ Customer Contract đã tồn tại cho {rec.name}, bỏ qua.")

            # 🔹 3. Tạo Dự toán nếu chưa có
            rec._create_cost_estimate_if_needed(project)

            rec.message_post(body=_("Chuyển giai đoạn: **Đang thực hiện**. Đã tạo Dự án, Hợp đồng khách hàng & Dự toán."))


    def action_to_completed(self):
        """Thực hiện → Hoàn thành"""
        self._ensure_from_stage(['executing'])
        self.date_completion = fields.Datetime.now()
        for rec in self:
            rec.stage = 'completed'
            rec.message_post(body=_("Chuyển giai đoạn: **Hoàn thành**."))

    def action_cancel(self):
        """Hủy hợp đồng + đẩy Project sang trạng thái 'Đã hủy' nếu có."""
        for contract in self:
            if contract.stage in ['completed', 'canceled']:
                continue
            contract.stage = 'canceled'
            if contract.project_id:
                canceled_stage = self.env['project.project.stage'].search([('name', '=', 'Đã hủy')], limit=1)
                if not canceled_stage:
                    raise UserError(_("Chưa cấu hình trạng thái Dự án 'Đã hủy'."))
                contract.project_id.stage_id = canceled_stage.id
            contract.message_post(body=_("**Đã hủy** hợp đồng."))

    # ---------- Sync sang Project khi sửa ----------
    def write(self, vals):
        res = super(ContractManagement, self).write(vals)
        # Sync một số trường sang Project
        for rec in self:
            if rec.project_id and any(k in vals for k in ['planned_start_date', 'planned_end_date', 'description', 'attachment_ids']):
                pj_vals = {}
                if 'planned_start_date' in vals:
                    pj_vals['date_start'] = rec.planned_start_date
                if 'planned_end_date' in vals:
                    pj_vals['date'] = rec.planned_end_date
                if 'description' in vals:
                    pj_vals['description'] = rec.description
                if pj_vals:
                    rec.project_id.write(pj_vals)

                if 'attachment_ids' in vals:
                    # làm gọn: xóa cũ & copy lại
                    olds = self.env['ir.attachment'].search([
                        ('res_model', '=', 'project.project'),
                        ('res_id', '=', rec.project_id.id)
                    ])
                    olds.unlink()
                    for att in rec.attachment_ids:
                        att.copy({'res_model': 'project.project', 'res_id': rec.project_id.id})
        return res
    def init(self):
        """Gán mặc định ngày thực hiện / hoàn thành = ngày tạo cho các hợp đồng cũ."""
        _logger.info("🔄 Updating old contract records without execution/completion dates...")
        self.env.cr.execute("""
            UPDATE contract_management
            SET date_execution = create_date::date
            WHERE date_execution IS NULL;
        """)
        self.env.cr.execute("""
            UPDATE contract_management
            SET date_completion = create_date::date
            WHERE date_completion IS NULL;
        """)
        _logger.info("✅ Done updating old contract dates.")



class ProjectTask(models.Model):
    _inherit = 'project.task'

    sale_order_line_id = fields.Many2one('sale.order.line', string="Bản báo giá", index=True)
    project_sale_order_id = fields.Many2one(related='project_id.sale_order_id', string="Hạng mục", store=True, readonly=True)

    @api.onchange('project_id')
    def _onchange_project_id_set_domain_for_sol(self):
        domain = [('id', '=', 0)]
        if self.project_id and self.project_id.sale_order_id:
            domain = [('order_id', '=', self.project_id.sale_order_id.id)]
        return {'domain': {'sale_order_line_id': domain}}

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        for rec in self:
            sol = rec.sale_order_line_id
            if not sol:
                continue
            if not rec.name or rec.name.lower() in ('new', 'mới', _('New').lower()):
                rec.name = sol.product_id.name or (sol.product_id.display_name if sol.product_id else False)
            if not rec.description:
                txt = sol.product_id.x_thong_so or (sol.product_id.description_sale or '')
                safe_txt = escape(txt).replace('\n', Markup('<br/>'))
                rec.description = Markup('<strong>Thông số:</strong><br/>') + safe_txt

    @api.constrains('sale_order_line_id', 'project_id')
    def _check_sol_belongs_to_project_so(self):
        for rec in self:
            if rec.sale_order_line_id and rec.project_id and rec.project_id.sale_order_id:
                if rec.sale_order_line_id.order_id != rec.project_id.sale_order_id:
                    raise ValidationError(_("Dòng đơn bán phải thuộc Đơn bán của Dự án."))


class ProjectProject(models.Model):
    _inherit = 'project.project'

    contract_id = fields.Many2one('contract.management', string='Hợp đồng')
    sale_order_id = fields.Many2one(
        'sale.order', string='Đơn bán',
        related='contract_id.sale_order_id', store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for pr in projects:
            if not pr.sale_order_id and pr.contract_id and pr.contract_id.sale_order_id:
                pr.sale_order_id = pr.contract_id.sale_order_id.id
        return projects

    def write(self, vals):
        res = super().write(vals)
        if 'contract_id' in vals and not vals.get('sale_order_id'):
            for pr in self.filtered(lambda r: not r.sale_order_id and r.contract_id and r.contract_id.sale_order_id):
                pr.sale_order_id = pr.contract_id.sale_order_id.id
        return res