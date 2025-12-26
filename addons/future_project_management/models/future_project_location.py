from odoo import models, fields, api


class FutureProjectLocation(models.Model):
    _name = "future.project.location"
    _description = "Future Project Location"
    _order = "name"

    # ======================
    # BASIC INFO
    # ======================
    name = fields.Char("Tên khu vực", required=True)
    description = fields.Text("Mô tả")

    # ======================
    # RELATION (BẮT BUỘC)
    # ======================
    project_ids = fields.One2many(
        "future.project",
        "location_id",
        string="Dự án",
    )

    # ======================
    # KPI (COMPUTE)
    # ======================
    project_count = fields.Integer(
        string="Tổng dự án",
        compute="_compute_counts",
    )

    won_project_count = fields.Integer(
        string="Dự án trúng thầu",
        compute="_compute_counts",
    )

    # ======================
    # COMPUTE LOGIC (CHUẨN)
    # ======================
    @api.depends(
        "project_ids",                      # thêm / xoá dự án
        "project_ids.active",               # archive / unarchive
        "project_ids.stage_id",             # đổi stage
        "project_ids.stage_id.is_won",      # đổi cờ trúng thầu
    )
    def _compute_counts(self):
        """
        Quy ước:
        - Chỉ đếm dự án đang theo dõi (active=True)
        - Trúng thầu = stage.is_won = True
        """
        for rec in self:
            active_projects = rec.project_ids.filtered(lambda p: p.active)

            rec.project_count = len(active_projects)

            rec.won_project_count = len(
                active_projects.filtered(
                    lambda p: p.stage_id and p.stage_id.is_won
                )
            )
