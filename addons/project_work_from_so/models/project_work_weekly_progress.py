# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProjectWorkWeeklyProgress(models.Model):
    _name = "project.work.weekly.progress"
    _description = "Báo cáo theo kỳ (nhập lũy kế)"
    _order = "assignment_id, period_no"

    _sql_constraints = [
        ("uniq_assignment_period", "unique(assignment_id, period_no)", "Mỗi phân công chỉ có 1 dòng cho mỗi kỳ."),
    ]

    assignment_id = fields.Many2one("project.work.assignment", string="Phân công", required=True, ondelete="cascade", index=True)

    # Related để dùng trong view / group / security
    user_id = fields.Many2one(related="assignment_id.user_id", store=True, readonly=True)
    project_id = fields.Many2one(related="assignment_id.project_id", store=True, readonly=True)
    work_item_id = fields.Many2one(related="assignment_id.work_item_id", store=True, readonly=True, index=True)

    # ✅ FIX lỗi của bạn: related đúng đường dẫn
    company_id = fields.Many2one(
        "res.company",
        related="assignment_id.project_id.company_id",
        store=True,
        readonly=True,
    )

    period_no = fields.Integer(string="Kỳ số", required=True, default=1)

    period_start = fields.Date(string="Từ ngày", compute="_compute_period", store=True)
    period_end = fields.Date(string="Đến ngày", compute="_compute_period", store=True)

    # alias cho view bạn đưa (date/qty)
    date = fields.Date(string="Date", compute="_compute_date", store=True)

    qty_cum = fields.Float(string="Lũy kế", default=0.0, digits="Product Unit of Measure")
    note = fields.Char(string="Ghi chú")

    qty_period = fields.Float(string="Sản lượng trong kỳ", compute="_compute_qty_period", store=False, digits="Product Unit of Measure")
    qty = fields.Float(string="Sản lượng", compute="_compute_qty_period", store=False, digits="Product Unit of Measure")  # alias

    is_locked = fields.Boolean(string="Đã khóa", compute="_compute_is_locked", store=False)

    @api.depends("period_end")
    def _compute_date(self):
        for rec in self:
            rec.date = rec.period_end

    @api.depends("assignment_id.date_start", "period_no")
    def _compute_period(self):
        for rec in self:
            if not rec.assignment_id or not rec.assignment_id.date_start or not rec.period_no:
                rec.period_start = False
                rec.period_end = False
                continue
            ps, pe = rec.assignment_id._get_period_dates(rec.period_no)
            rec.period_start = ps
            rec.period_end = pe

    @api.depends("assignment_id", "period_no", "qty_cum")
    def _compute_qty_period(self):
        for rec in self:
            if not rec.assignment_id or not rec.period_no:
                rec.qty_period = rec.qty or (rec.qty_cum or 0.0)
                rec.qty = rec.qty_period
                continue
            prev = self.search([
                ("assignment_id", "=", rec.assignment_id.id),
                ("period_no", "<", rec.period_no),
            ], order="period_no desc", limit=1)
            prev_cum = prev.qty_cum if prev else 0.0
            rec.qty_period = (rec.qty_cum or 0.0) - prev_cum
            rec.qty = rec.qty_period

    @api.depends("assignment_id.date_start", "period_no")
    def _compute_is_locked(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.assignment_id or not rec.assignment_id.date_start:
                rec.is_locked = False
                continue
            cur_no = rec.assignment_id._get_current_period_no(today=today)
            rec.is_locked = (rec.period_no != cur_no)

    def _can_edit_locked(self):
        return self.env.user.has_group("project.group_project_manager") or self.env.user.has_group("base.group_system")

    def _check_lock(self, vals):
        if self._can_edit_locked():
            return
        if not (set(vals.keys()) & {"qty_cum", "note"}):
            return
        today = fields.Date.context_today(self)
        for rec in self:
            cur_no = rec.assignment_id._get_current_period_no(today=today)
            if rec.period_no != cur_no:
                raise UserError(_("Chỉ được nhập/sửa kỳ hiện tại (kỳ %s).") % cur_no)

    @api.constrains("qty_cum", "assignment_id", "period_no")
    def _check_monotonic(self):
        for rec in self:
            if rec.period_no <= 1:
                continue
            prev = self.search([
                ("assignment_id", "=", rec.assignment_id.id),
                ("period_no", "<", rec.period_no),
            ], order="period_no desc", limit=1)
            if prev and (rec.qty_cum or 0.0) < (prev.qty_cum or 0.0):
                raise ValidationError(_("Lũy kế kỳ %s phải >= lũy kế kỳ %s.") % (rec.period_no, prev.period_no))

    def write(self, vals):
        self._check_lock(vals)
        return super().write(vals)

    def unlink(self):
        if not self._can_edit_locked():
            raise UserError(_("Không được xóa lịch sử báo cáo kỳ."))
        return super().unlink()
