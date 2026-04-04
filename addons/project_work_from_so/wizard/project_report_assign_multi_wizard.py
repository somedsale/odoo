# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ProjectReportAssignMultiWizard(models.TransientModel):
    _name = "project.report.assign.multi.wizard"
    _description = "Phân công người báo cáo sản lượng cho nhiều dự án"

    user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo sản lượng",
        required=True,
        domain="[('share', '=', False)]",
    )

    project_ids = fields.Many2many(
        "project.project",
        string="Dự án",
    )

    project_count = fields.Integer(
        string="Số dự án",
        compute="_compute_project_count",
    )

    @api.depends("project_ids")
    def _compute_project_count(self):
        for rec in self:
            rec.project_count = len(rec.project_ids)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            res["project_ids"] = [(6, 0, active_ids)]
        return res

    def action_confirm_assign(self):
        self.ensure_one()

        if not self.project_ids:
            raise UserError(_("Vui lòng chọn ít nhất một dự án."))

        return self.project_ids.action_assign_project_report_user_multi(self.user_id.id)