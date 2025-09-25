from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class WizardCreateTasks(models.TransientModel):
    _name = "wizard.create.tasks.from.sale"
    _description = "Create tasks from selected sale.order.line"

    sale_order_line_ids = fields.Many2many(
        "sale.order.line",
        "wizard_sol_rel", "wizard_id", "line_id",
        string="Bảng dòng đơn hàng",
        domain="[('order_id', '=', sale_order_id)]",
    )

    sale_order_id = fields.Many2one(
        "sale.order",
        string="Báo giá",
        readonly=True
    )
    used_line_ids = fields.Many2many("sale.order.line", compute="_compute_used_lines")
    @api.depends('sale_order_id', 'sale_order_line_ids')
    def _compute_used_lines(self):
        for wizard in self:
            project = self.env["project.project"].browse(self.env.context.get("active_id"))
            if project and project.sale_order_id:
                used = self.env["project.task"].search([
                    ("project_id", "=", project.id),
                    ("sale_order_line_id", "!=", False),
                ]).mapped("sale_order_line_id")
                _logger.warning(">>>> USED LINES: %s", used.ids)
                wizard.used_line_ids = used
            else:
                wizard.used_line_ids = False
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)

        project = self.env["project.project"].browse(self.env.context.get("active_id"))
        if project and project.sale_order_id:
            used_line_ids = self.env["project.task"].search([
                ("project_id", "=", project.id),
                ("sale_order_line_id", "!=", False),
            ]).mapped("sale_order_line_id.id")

            lines = self.env["sale.order.line"].search([
                ("order_id", "=", project.sale_order_id.id),
                ("id", "not in", used_line_ids),
            ])
            res["sale_order_id"] = project.sale_order_id.id
            res["sale_order_line_ids"] = [(6, 0, lines.ids)]
        return res

    def action_create_tasks(self):
        if not self.sale_order_line_ids:
            return
        project = self.env["project.project"].browse(self._context.get("active_id"))

        created_tasks = self.env["project.task"]
        for line in self.sale_order_line_ids:
            task = self.env["project.task"].create({
                "name": line.name,
                "project_id": project.id,
                "sale_order_line_id": line.id,
            })
            created_tasks |= task

        # Sau khi tạo xong → show notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Tạo thành công",
                "message": f"Đã tạo {len(created_tasks)} nhiệm vụ cho dự án {project.name}",
                "sticky": False,  # False = tự biến mất, True = phải bấm tắt
            }
        }