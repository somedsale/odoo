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
        domain="[('order_id', '=', sale_order_id), ('display_type', '=', False)]",
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
        res["sale_order_line_ids"] = [(5, 0, 0)]  # Xóa hết mặc định, không tick sẵn
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
                "partner_id": project.partner_id.id if project.partner_id else False,
                "user_ids": [(5, 0, 0)],
            })
            created_tasks |= task

        # gửi notification qua bus
        self.env['bus.bus']._sendone(
            self.env.user.partner_id,
            "simple_notification",
            {
                "title": "Tạo thành công",
                "message": f"Đã tạo {len(created_tasks)} nhiệm vụ cho dự án {project.name}",
                "sticky": False,
                "type": "success",
            }
        )

        # đóng wizard
        # return {"type": "ir.actions.act_window_close"}
        action = self.env.ref("project.act_project_project_2_project_task_all").sudo().read()[0]
        action.update({
            "domain": [("project_id", "=", project.id)],
            "context": dict(self.env.context, default_project_id=project.id),
        })
        return action