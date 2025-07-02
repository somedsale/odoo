from odoo import models
import logging

_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super(SaleOrder, self).action_confirm()
        for order in self:
            if order.state == 'sale':
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
                _logger.info(f"Creating project with values: {project_vals}")
                self.env['project.project'].create(project_vals)
        return res