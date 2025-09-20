# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging
from markupsafe import Markup, escape

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    contract_id = fields.Many2one('contract.management', string='Contract', readonly=True)

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if not order.contract_id:
                # Create contract when sale order is confirmed
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
    _inherit = ['mail.thread', 'mail.activity.mixin']  # Enable chatter for tracking
    _order = 'create_date desc'
    name = fields.Char(string='Tên hợp đồng', required=True)
    num_contract = fields.Char(string='Số hợp đồng')
    contract_value = fields.Float(string='Giá trị hợp đồng')
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True)
    stage = fields.Selection([
        ('negotiating', 'Đang thương thảo hợp đồng'),
        ('preparing', 'Chuẩn bị thực hiện'),
        ('executing', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('canceled', 'Đã hủy'),
    ], string='Giai đoạn', default='negotiating', required=True)
    project_id = fields.Many2one('project.project', string='Dự án', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    planned_start_date = fields.Date(string='Ngày bắt đầu')
    planned_end_date = fields.Date(string='Ngày kết thúc')
    description = fields.Text(string='Mô tả')
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu')

    @api.model
    def _get_next_stage(self, current_stage):
        stages = ['negotiating', 'preparing', 'executing', 'completed']
        current_index = stages.index(current_stage) if current_stage in stages else -1
        return stages[current_index + 1] if current_index < len(stages) - 1 else current_stage

    def action_next_stage(self):
        for contract in self:
            if contract.stage not in ['completed', 'canceled']:
                next_stage = self._get_next_stage(contract.stage)
                contract.stage = next_stage
                if next_stage == 'executing' and not contract.project_id:
                    # Define task stages
                    task_stage_refs = [
                        'contract_management.task_type_new_order',
                        'contract_management.task_type_purchase',
                        'contract_management.task_type_production',
                        'contract_management.task_type_delivery',
                        'contract_management.task_type_installation',
                        'contract_management.task_type_acceptance',
                        'contract_management.task_type_completed',
                    ]
                    task_stages = self.env['project.task.type']
                    for ref in task_stage_refs:
                        try:
                            stage = self.env.ref(ref)
                            task_stages |= stage
                        except ValueError:
                            raise UserError(f"Task stage {ref} not found. Please ensure all task stages are defined.")
                    if contract.sale_order_id.x_project_name:
                        name_project = f"Số HĐ {contract.num_contract or '...'} - {contract.sale_order_id.x_project_name}"
                    else:
                        name_project = contract.sale_order_id.name
                    # Create project when stage is 'Đang thực hiện'
                    project_vals = {
                        'name': f'{name_project}',
                        'partner_id': contract.partner_id.id,
                        'company_id': contract.company_id.id,
                        'contract_id': contract.id,
                        # 'sale_order_id': contract.sale_order_id.id,
                        'allow_timesheets': False,  # Optional: Disable timesheets if not needed
                        'allow_billable': False,  # Optional: Disable billing if not needed  # Optional: Disable billing if not needed
                        'type_ids': [(6, 0, task_stages.ids)],  # Assign task stages to project
                        'date_start': contract.planned_start_date,  # Sync planned start date
                        'date': contract.planned_end_date,  # Sync planned end date
                        'description': contract.description,  # Sync description
                    }
                    manager_id = self.env['hr.department'].get_manager_id_by_name('Kế hoạch - Sản xuất')
                    if manager_id:
                        project_vals['user_id'] = manager_id.user_id.id
                        _logger.info(f"Project Manager assigned: {manager_id}")
                    else:
                        _logger.info("No Project Manager assigned")
                    
                    # Tạo dự án
                    project = self.env['project.project'].create(project_vals)
                    contract.project_id = project.id

                    # Sync attachments to project
                    if contract.attachment_ids:
                        for attachment in contract.attachment_ids:
                            attachment.copy({
                                'res_model': 'project.project',
                                'res_id': project.id,
                            })

                    
                    if not contract.sale_order_id.cost_estimate_id:
                        # Tạo dự toán
                        budget_vals = {
                            'name': f'Dự toán cho {name_project}',
                            'sale_order_id': contract.sale_order_id.id,
                            'project_id': project.id,
                            # 'currency_id': order.currency_id.id,
                            'line_ids': [
                                (0, 0, {
                                    'product_id': line.product_id.id,
                                    'unit': line.product_uom.id,
                                    'quantity': line.product_uom_qty,
                                    'sale_order_line_id': line.id,
                                    # 'task_id': product_task_map.get(line.product_id.id),
                                })
                                for line in contract.sale_order_id.order_line
                                if line.product_id
                            ],
                        }
                        cost_estimate = self.env['cost.estimate'].create(budget_vals)
                        contract.sale_order_id.cost_estimate_id = cost_estimate.id                     

    def action_cancel(self):
        for contract in self:
            if contract.stage not in ['completed', 'canceled']:
                contract.stage = 'canceled'
                if contract.project_id:
                    # Find the 'Đã hủy' stage for the project
                    canceled_stage = self.env['project.project.stage'].search([
                        ('name', '=', 'Đã hủy')
                    ], limit=1)
                    if not canceled_stage:
                        raise UserError("Project stage 'Đã hủy' not found. Please ensure it is defined.")
                    contract.project_id.stage_id = canceled_stage.id

    def write(self, vals):
        res = super(ContractManagement, self).write(vals)
        # Sync changes to the project if it exists
        if any(field in vals for field in ['planned_start_date', 'planned_end_date', 'description', 'attachment_ids']) and self.project_id:
            project_vals = {}
            if 'planned_start_date' in vals:
                project_vals['date_start'] = vals.get('planned_start_date')
            if 'planned_end_date' in vals:
                project_vals['date'] = vals.get('planned_end_date')
            if 'description' in vals:
                project_vals['description'] = vals.get('description')
            if project_vals:
                self.project_id.write(project_vals)
            if 'attachment_ids' in vals:
                # Remove old attachments linked to the project
                old_attachments = self.env['ir.attachment'].search([
                    ('res_model', '=', 'project.project'),
                    ('res_id', '=', self.project_id.id)
                ])
                old_attachments.unlink()
                # Copy new attachments to the project
                for attachment in self.attachment_ids:
                    attachment.copy({
                        'res_model': 'project.project',
                        'res_id': self.project_id.id,
                    })
        return res

class ProjectTask(models.Model):
    _inherit = 'project.task'

    sale_order_line_id = fields.Many2one('sale.order.line', string="Bản báo giá", index=True)
    project_sale_order_id = fields.Many2one(related='project_id.sale_order_id', string="Hạng mục", store=True, readonly=True)

    @api.onchange('project_id')
    def _onchange_project_id_set_domain_for_sol(self):
        """Khi chọn/đổi dự án, giới hạn SOL theo SO của dự án."""
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
                # escape để an toàn, rồi thay \n bằng <br/> và ghép nhãn “Thông số:”
                safe_txt = escape(txt).replace('\n', Markup('<br/>'))
                rec.description = Markup('<strong>Thông số:</strong><br/>') + safe_txt
            # if not rec.planned_hours:
            #     rec.planned_hours = sol.product_uom_qty or 0.0

    @api.constrains('sale_order_line_id', 'project_id')
    def _check_sol_belongs_to_project_so(self):
        for rec in self:
            if rec.sale_order_line_id and rec.project_id and rec.project_id.sale_order_id:
                if rec.sale_order_line_id.order_id != rec.project_id.sale_order_id:
                    raise ValidationError(_("Dòng đơn bán phải thuộc Đơn bán của Dự án."))
class ProjectProject(models.Model):
    _inherit = 'project.project'

    contract_id = fields.Many2one('contract.management', string='Hợp đồng')
    # Tự lấy từ hợp đồng, lưu DB để dùng domain/ tìm kiếm
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn bán',
        related='contract_id.sale_order_id',
        store=True, readonly=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        # Đồng bộ SO từ contract (phòng khi chỗ tạo project quên set)
        for pr in projects:
            if not pr.sale_order_id and pr.contract_id and pr.contract_id.sale_order_id:
                pr.sale_order_id = pr.contract_id.sale_order_id.id
        return projects

    def write(self, vals):
        res = super().write(vals)
        # Nếu sau này contract_id mới được gán, tự set sale_order_id theo
        if 'contract_id' in vals and not vals.get('sale_order_id'):
            for pr in self.filtered(lambda r: not r.sale_order_id and r.contract_id and r.contract_id.sale_order_id):
                pr.sale_order_id = pr.contract_id.sale_order_id.id
        return res