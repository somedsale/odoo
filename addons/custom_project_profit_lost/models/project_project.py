from odoo import models, fields, api

class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_internal_project2 = fields.Boolean(
        string="Dự án nội bộ",
        default=False,
        help="Chỉ dùng để quản lý công việc nội bộ, không theo dõi lời/lỗ."
    )

    @api.model
    def create(self, vals):
        project = super().create(vals)
        # nếu là dự án nội bộ => KHÔNG tạo profit.lost
        if not vals.get('is_internal_project2', False):
            self.env['project.profit.lost'].create_or_update(project.id)
        return project
    def write(self, vals):
        res = super().write(vals)

        # Chỉ khi thay đổi field is_internal_project2 thì mới sync lại toàn bộ
        if 'is_internal_project2' in vals:
            self.env['project.profit.lost'].load_all_projects()

        return res
