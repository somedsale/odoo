from odoo import models,fields
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    project_id = fields.Many2one('project.project', string='Dự án', readonly=True)
    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.state == 'sale':
                # Tạo dự án
                if order.x_project_name:
                    name_project = order.x_project_name + ' - ' + order.name
                else:
                    name_project = order.name
                project_vals = {
                    'name': name_project,
                    'partner_id': order.partner_id.id,
                    'company_id': order.company_id.id,
                }
                config = self.env['project.config'].search([], limit=1)
                if config and config.default_project_manager_id:
                    project_vals['user_id'] = config.default_project_manager_id.id
                    _logger.info(f"Using Default Project Manager: {config.default_project_manager_id.name}")
                else:
                    _logger.info("No Project Manager assigned")
                
                # Tạo dự án
                project = self.env['project.project'].create(project_vals)
                
                # Danh sách các giai đoạn
                stage_names = [
                    'Đơn đặt hàng mới',
                    'Mua Hàng',
                    'Sản xuất',
                    'Giao hàng',
                    'Lắp đặt',
                    'Nghiệm thu',
                    'Hoàn thành'
                ]

                # Tạo các giai đoạn cho dự án
                stage_dict = {}
                sequence = 0
                for stage_name in stage_names:
                    stage_vals = {
                        'name': stage_name,
                        'sequence': sequence,
                        'project_ids': [(4, project.id)],  # Gắn giai đoạn vào dự án
                    }
                    stage = self.env['project.task.type'].create(stage_vals)
                    stage_dict[stage_name] = stage
                    _logger.info(f"Created stage: {stage_name} for project: {project.name}")
                    sequence += 10

                # Tạo nhiệm vụ cho các sản phẩm tiêu dùng trong giai đoạn "Đơn đặt hàng mới"
                new_order_stage = stage_dict.get('Đơn đặt hàng mới')
                if new_order_stage:
                    for line in order.order_line:
                        if line.product_id.product_tmpl_id.type == 'consu':
                            task_vals = {
                                'name': f"Task for {line.product_id.name}",
                                'project_id': project.id,
                                'stage_id': new_order_stage.id,
                                'partner_id': order.partner_id.id,
                            }
                            self.env['project.task'].create(task_vals)
                            _logger.info(f"Created task for product: {line.product_id.name} in stage: Đơn đặt hàng mới")
                        else:
                            _logger.info(f"Skipped product: {line.product_id.name} (not consumable)")
                if not order.cost_estimate_id:
                    # Tạo dự toán
                    budget_vals = {
                        'name': f'Dự toán cho {name_project}',
                        'sale_order_id': order.id,
                        'project_id': project.id,
                        'currency_id': order.currency_id.id,
                        'line_ids': [
                            (0, 0, {
                                'product_id': line.product_id.id,
                                'unit': line.product_uom.id,
                                'quantity': line.product_uom_qty,
                                'price_unit': 0.0,
                            })
                            for line in order.order_line
                            if line.product_id and line.product_id.product_tmpl_id.type == 'consu'
                        ],
                    }
                    cost_estimate = self.env['cost.estimate'].create(budget_vals)
                    order.cost_estimate_id = cost_estimate.id
        return res