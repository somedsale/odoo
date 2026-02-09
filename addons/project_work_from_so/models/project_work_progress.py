# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectWorkProgress(models.Model):
    _name = "project.work.progress"
    _description = "Work Progress Per Period"
    _order = "assignment_id, period_no"

    assignment_id = fields.Many2one("project.work.assignment", required=True, ondelete="cascade", index=True)

    project_id = fields.Many2one(related="assignment_id.project_id", store=True, readonly=True)
    work_item_id = fields.Many2one(related="assignment_id.work_item_id", store=True, readonly=True)
    user_id = fields.Many2one(related="assignment_id.user_id", store=True, readonly=True)
    company_id = fields.Many2one(related="assignment_id.company_id", store=True, readonly=True)

    period_no = fields.Integer(string="Kỳ", required=True, index=True)
    period_start = fields.Date(string="Từ ngày", compute="_compute_period", store=True)
    period_end = fields.Date(string="Đến ngày", compute="_compute_period", store=True)

    qty_cum = fields.Float(string="Lũy kế", digits="Product Unit of Measure", default=0.0)
    qty_period = fields.Float(string="Sản lượng kỳ", compute="_compute_qty_period", store=True, digits="Product Unit of Measure")

    note = fields.Text(string="Ghi chú")

    _sql_constraints = [
        ("uniq_assignment_period", "unique(assignment_id, period_no)", "Mỗi kỳ chỉ có 1 dòng tiến độ."),
    ]

    @api.depends("assignment_id.date_start", "period_no")
    def _compute_period(self):
        for rec in self:
            if not rec.assignment_id or not rec.assignment_id.date_start or not rec.period_no:
                rec.period_start = False
                rec.period_end = False
                continue
            ps, pe = rec.assignment_id._get_period_bounds(rec.assignment_id.date_start, rec.period_no)
            rec.period_start = ps
            rec.period_end = pe

    @api.depends("qty_cum", "period_no", "assignment_id", "assignment_id.progress_ids.qty_cum")
    def _compute_qty_period(self):
        for rec in self:
            prev = self.search(
                [("assignment_id", "=", rec.assignment_id.id), ("period_no", "<", rec.period_no)],
                order="period_no desc",
                limit=1,
            )
            prev_cum = prev.qty_cum if prev else 0.0
            diff = (rec.qty_cum or 0.0) - prev_cum
            rec.qty_period = max(0.0, diff)

    def _prev_cum_for(self, assignment_id, period_no):
        prev = self.search(
            [("assignment_id", "=", assignment_id), ("period_no", "<", period_no)],
            order="period_no desc",
            limit=1,
        )
        return prev.qty_cum if prev else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        safe_list = []
        for vals in vals_list:
            assignment_id = vals.get("assignment_id")
            period_no = vals.get("period_no")
            qty_cum = vals.get("qty_cum", 0.0) or 0.0
            if assignment_id and period_no:
                prev_cum = self._prev_cum_for(assignment_id, period_no)
                # Clamp để không bao giờ giảm
                if qty_cum < prev_cum:
                    qty_cum = prev_cum
                vals["qty_cum"] = qty_cum
            safe_list.append(vals)
        return super().create(safe_list)

    def write(self, vals):
        # Vì vals dùng chung cho nhiều record => xử lý theo từng record để clamp đúng
        for rec in self:
            safe_vals = dict(vals)

            # nếu đang sửa note thôi nhưng bản thân qty_cum đã < prev -> cũng phải sửa lại tránh nổ validate
            new_qty = safe_vals.get("qty_cum", rec.qty_cum or 0.0) or 0.0
            prev_cum = rec._prev_cum_for(rec.assignment_id.id, rec.period_no)
            if new_qty < prev_cum:
                new_qty = prev_cum
                safe_vals["qty_cum"] = new_qty

            super(ProjectWorkProgress, rec).write(safe_vals)

        return True

    @api.constrains("qty_cum")
    def _check_monotonic(self):
        """Giữ lại để bảo vệ – nhưng vì create/write đã clamp nên sẽ không còn nổ."""
        for rec in self:
            prev_cum = rec._prev_cum_for(rec.assignment_id.id, rec.period_no)
            if (rec.qty_cum or 0.0) < prev_cum:
                raise ValidationError(
                    f"Lũy kế kỳ {rec.period_no} phải >= lũy kế kỳ {rec.period_no - 1}."
                )
