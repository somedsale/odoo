# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

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
                    'name': f'Contract for {order.name}',
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

    name = fields.Char(string='Tên hợp đồng', required=True)
    sale_order_id = fields.Many2one('sale.order', string='Đơn hàng', required=True)
    partner_id = fields.Many2one('res.partner', string='Khách hàng', required=True)
    stage = fields.Selection([
        ('negotiating', 'Đang thương thảo hợp đồng'),
        ('preparing', 'Chuẩn bị thực hiện'),
        ('executing', 'Đang thực hiện'),
        ('completed', 'Hoàn thành'),
        ('canceled', 'Đã hủy'),
    ], string='Giai đoạn', default='negotiating', required=True, tracking=True)
    project_id = fields.Many2one('project.project', string='Dự án', readonly=True)
    company_id = fields.Many2one('res.company', string='Công ty', default=lambda self: self.env.company)
    planned_start_date = fields.Date(string='Ngày bắt dầu', tracking=True)
    planned_end_date = fields.Date(string='Ngày kết thúc', tracking=True)
    description = fields.Text(string='Mô tả', tracking=True)
    attachment_ids = fields.Many2many('ir.attachment', string='Tài liệu', tracking=True)

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
                        name_project = contract.sale_order_id.x_project_name + ' - ' + contract.sale_order_id.name
                    else:
                        name_project = contract.sale_order_id.name
                    # Create project when stage is 'Đang thực hiện'
                    project_vals = {
                        'name': f'{name_project} - {contract.name}',
                        'partner_id': contract.partner_id.id,
                        'company_id': contract.company_id.id,
                        'allow_timesheets': False,  # Optional: Disable timesheets if not needed
                        'allow_billable': True,  # Optional: Disable billing if not needed
                        'type_ids': [(6, 0, task_stages.ids)],  # Assign task stages to project
                        'date_start': contract.planned_start_date,  # Sync planned start date
                        'date': contract.planned_end_date,  # Sync planned end date
                        'description': contract.description,  # Sync description
                    }
                    config = self.env['project.config'].search([], limit=1)
                    if config and config.default_project_manager_id:
                        project_vals['user_id'] = config.default_project_manager_id.id
                        _logger.info(f"Using Default Project Manager: {config.default_project_manager_id.name}")
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

                    # Create tasks from sale order lines
                    default_stage = self.env['project.task.type'].search([
                        ('name', '=', 'Đơn đặt hàng mới'),
                        ('project_ids', 'in', project.id)
                    ], limit=1)
                    if not default_stage:
                        raise UserError("Default task stage 'Đơn đặt hàng mới' not found for the project.")
                    product_task_map = {}
                    for line in contract.sale_order_id.order_line:
                        if line.product_id.product_tmpl_id.type == 'consu':  # Ensure product exists
                            task_vals = {
                                'name': f"{line.product_id.name} - {line.product_uom_qty} {line.product_uom.name}",
                                'project_id': project.id,
                                'partner_id': contract.partner_id.id,
                                'quantity': line.product_uom_qty,
                                'uom_id': line.product_uom.id,
                                'stage_id': default_stage.id,
                                'allow_billable': True,
                                'description': line.name,  # Use sale order line description
                                'user_ids': [(6, 0, [config.default_project_manager_id.id])]
                            }
                            task = self.env['project.task'].create(task_vals)
                            product_task_map[line.product_id.id] = task.id 
                    
                    # Tạo nhiệm vụ cho các sản phẩm tiêu dùng trong giai đoạn "Đơn đặt hàng mới"

                    
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
                                    'task_id': product_task_map.get(line.product_id.id),
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

    @api.model
    def write(self, vals):
        res = super(ProjectTask, self).write(vals)
        if 'stage_id' in vals:
            for task in self:
                if task.project_id:
                    # Find the contract linked to the project
                    contract = self.env['contract.management'].search([
                        ('project_id', '=', task.project_id.id)
                    ], limit=1)
                    if contract and contract.stage not in ['completed', 'canceled']:
                        # Check if all tasks in the project are in 'Hoàn thành' stage
                        completed_stage = self.env['project.task.type'].search([
                            ('name', '=', 'Hoàn thành'),
                            ('project_ids', 'in', task.project_id.id)
                        ], limit=1)
                        if completed_stage:
                            all_tasks_completed = all(
                                t.stage_id.id == completed_stage.id
                                for t in self.env['project.task'].search([
                                    ('project_id', '=', task.project_id.id)
                                ])
                            )
                            if all_tasks_completed:
                                # Update contract stage to 'Hoàn thành'
                                contract.stage = 'completed'
                                # Update project stage to 'Hoàn tất'
                                completed_project_stage = self.env['project.project.stage'].search([
                                    ('name', '=', 'Hoàn tất')
                                ], limit=1)
                                if not completed_project_stage:
                                    raise UserError("Project stage 'Hoàn tất' not found. Please ensure it is defined.")
                                task.project_id.stage_id = completed_project_stage.id
        return res

class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model
    def write(self, vals):
        res = super(ProjectProject, self).write(vals)
        if 'stage_id' in vals:
            for project in self:
                # Find the contract linked to the project
                contract = self.env['contract.management'].search([
                    ('project_id', '=', project.id)
                ], limit=1)
                if contract and contract.stage not in ['completed', 'canceled']:
                    # Check if the project stage is 'Đã hủy'
                    canceled_stage = self.env['project.project.stage'].search([
                        ('name', '=', 'Đã hủy')
                    ], limit=1)
                    if canceled_stage and project.stage_id.id == canceled_stage.id:
                        contract.stage = 'canceled'
        return res