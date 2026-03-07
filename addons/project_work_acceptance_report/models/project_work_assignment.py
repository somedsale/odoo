# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectWorkAssignment(models.Model):
    _inherit = "project.work.assignment"

    # =========================
    # Người báo cáo nghiệm thu (khác người thi công)
    # =========================
    acceptance_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo nghiệm thu",
        tracking=True,
        help="Người phụ trách báo cáo nghiệm thu cho phân công này.",
    )

    # Người thi công lấy từ hạng mục (nếu bạn dùng assigned_user_id ở work item)
    executor_user_id = fields.Many2one(
        "res.users",
        related="work_item_id.assigned_user_id",
        string="Người thi công",
        readonly=True,
        store=False,
    )

    # =========================
    # Lịch sử nghiệm thu theo kỳ
    # =========================
    acceptance_progress_ids = fields.One2many(
        "project.work.acceptance.progress",
        "assignment_id",
        string="Lịch sử nghiệm thu theo kỳ",
    )

    # =========================
    # Thông tin hiển thị cho view report
    # =========================
    work_item_name = fields.Char(
        string="Hạng mục",
        related="work_item_id.name",
        readonly=True,
        store=False,
    )
    product_id = fields.Many2one(
        "product.product",
        related="work_item_id.product_id",
        readonly=True,
        store=False,  # để searchpanel tránh dùng field này
    )
    uom_id = fields.Many2one(
        "uom.uom",
        related="work_item_id.uom_id",
        readonly=True,
        store=False,
    )
    qty_plan = fields.Float(
        string="Khối lượng kế hoạch",
        related="work_item_id.qty_plan",
        readonly=True,
        store=False,
    )
    progress_percent = fields.Float(
        string="% hoàn thành sản lượng",
        related="work_item_id.progress_percent",
        readonly=True,
        store=False,
    )

    value_completed = fields.Float(
        string="Giá trị sản lượng hoàn thành",
        compute="_compute_acceptance_display_values",
        readonly=True,
        store=False,
    )
    price_unit = fields.Float(
        string="Đơn giá hạng mục",
        compute="_compute_acceptance_display_values",
        readonly=True,
        store=False,
    )

    # =========================
    # Kỳ hiện tại
    # =========================
    current_period_no = fields.Integer(
        string="Kỳ hiện tại",
        compute="_compute_acceptance_current_period",
        readonly=True,
        store=False,
    )
    current_period_start = fields.Date(
        string="Từ ngày",
        compute="_compute_acceptance_current_period",
        readonly=True,
        store=False,
    )
    current_period_end = fields.Date(
        string="Đến ngày",
        compute="_compute_acceptance_current_period",
        readonly=True,
        store=False,
    )

    # =========================
    # Nhập liệu nghiệm thu kỳ hiện tại
    # =========================
    prev_acceptance_qty_cum = fields.Float(
        string="Lũy kế nghiệm thu kỳ trước",
        compute="_compute_acceptance_current_values",
        readonly=True,
        store=False,
        digits="Product Unit of Measure",
    )
    current_acceptance_qty_cum = fields.Float(
        string="Lũy kế nghiệm thu hiện tại",
        compute="_compute_acceptance_current_values",
        readonly=True,
        store=False,
        digits="Product Unit of Measure",
    )
    current_acceptance_qty_period = fields.Float(
        string="Khối lượng nghiệm thu trong kỳ",
        compute="_compute_acceptance_current_values",
        inverse="_inverse_current_acceptance_qty_period",
        store=False,
        digits="Product Unit of Measure",
    )
    current_acceptance_qty_remaining = fields.Float(
        string="Khối lượng còn lại",
        compute="_compute_acceptance_current_values",
        readonly=True,        store=False,
        digits="Product Unit of Measure",
    )

    current_acceptance_note = fields.Text(
        string="Ghi chú nghiệm thu kỳ hiện tại",
        compute="_compute_acceptance_current_values",
        inverse="_inverse_current_acceptance_note",
        store=False,
    )
    acceptance_value_prev_period = fields.Float(
        string="Giá trị nghiệm thu kỳ trước",
        compute="_compute_acceptance_amounts",
        readonly=True,
        store=False,    )
    acceptance_value_current_period = fields.Float(
        string="Giá trị nghiệm thu kỳ này",
        compute="_compute_acceptance_amounts",
        readonly=True,
        store=False,
    )
    acceptance_value_cum = fields.Float(
        string="Lũy kế giá trị nghiệm thu",
        compute="_compute_acceptance_amounts",
        readonly=True,
        store=False,
    )
    current_acceptance_value_remaining = fields.Float(
        string="Giá trị còn lại",
        compute="_compute_acceptance_amounts",
        readonly=True,        store=False,    )
    acceptance_process_percent = fields.Float(
        string="% Nghiệm thu",
        compute="_compute_acceptance_amounts",
        readonly=True,        store=False,
    )
    # -------------------------
    # Ràng buộc nghiệp vụ
    # -------------------------
    # @api.constrains("acceptance_user_id", "work_item_id")
    # def _check_acceptance_user_not_executor(self):
    #     for rec in self:
    #         if rec.acceptance_user_id and rec.work_item_id and rec.work_item_id.assigned_user_id:
    #             if rec.acceptance_user_id in rec.work_item_id.assigned_user_id:
    #                 raise ValidationError("Người báo cáo nghiệm thu phải khác người thi công của hạng mục.")

    # -------------------------
    # Helpers giá trị hiển thị
    # -------------------------
    @api.depends("work_item_id")
    def _compute_acceptance_display_values(self):
        for rec in self:
            pu = 0.0
            wi = rec.work_item_id
            if wi:
                if "price_unit" in wi._fields:
                    pu = wi.price_unit or 0.0
                elif "price_subtotal" in wi._fields and (wi.qty_settlement or 0.0):
                    pu = (wi.price_subtotal or 0.0) / wi.qty_settlement if wi.qty_settlement else 0.0
            rec.price_unit = pu

            if wi and "value_completed" in wi._fields:
                rec.value_completed = wi.value_completed or 0.0
            else:
                qty_done = getattr(wi, "qty_done", 0.0) if wi else 0.0
                rec.value_completed = (qty_done or 0.0) * pu

    # -------------------------
    # Helpers kỳ báo cáo (giống quyết toán)
    # -------------------------
    def _acceptance_get_period_bounds_fallback(self, date_start, period_no):
        start = fields.Date.to_date(date_start)
        if period_no == 1:
            weekday = start.weekday()  # Mon=0..Sun=6
            delta = max(0, 5 - weekday)  # tới T7
            ps = start
            pe = start + timedelta(days=delta)
        else:
            base_mon = start - timedelta(days=start.weekday())
            ps = base_mon + timedelta(weeks=period_no - 1)
            pe = ps + timedelta(days=5)  # T2 -> T7
        return ps, pe

    def _acceptance_get_period_bounds(self, date_start, period_no):
        self.ensure_one()
        if hasattr(super(ProjectWorkAssignment, self), "_get_period_bounds"):
            try:
                return super(ProjectWorkAssignment, self)._get_period_bounds(date_start, period_no)
            except Exception:
                pass
        return self._acceptance_get_period_bounds_fallback(date_start, period_no)

    def _acceptance_compute_current_period_no_from_date(self, d):
        self.ensure_one()
        if not self.date_start or not d:
            return 0
        start = fields.Date.to_date(self.date_start)
        d = fields.Date.to_date(d)
        if d < start:
            return 0

        p1s, p1e = self._acceptance_get_period_bounds(start, 1)
        if p1s <= d <= p1e:
            return 1

        base_mon = start - timedelta(days=start.weekday())
        k2_start = base_mon + timedelta(weeks=1)
        if d < k2_start:
            return 1
        weeks = ((d - k2_start).days // 7)
        return 2 + max(0, weeks)

    @api.depends("date_start")
    def _compute_acceptance_current_period(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.date_start:
                rec.current_period_no = 0
                rec.current_period_start = False
                rec.current_period_end = False
                continue

            period_no = rec._acceptance_compute_current_period_no_from_date(today)
            rec.current_period_no = period_no
            if period_no:
                ps, pe = rec._acceptance_get_period_bounds(rec.date_start, period_no)
                rec.current_period_start = ps
                rec.current_period_end = pe
            else:
                rec.current_period_start = False
                rec.current_period_end = False

    # -------------------------
    # Helpers dữ liệu acceptance progress
    # -------------------------
    def _get_or_create_acceptance_progress(self, period_no):
        self.ensure_one()
        Progress = self.env["project.work.acceptance.progress"]
        rec = Progress.search([
            ("assignment_id", "=", self.id),
            ("period_no", "=", period_no),
        ], limit=1)
        if rec:
            return rec
        return Progress.create({
            "assignment_id": self.id,
            "period_no": period_no,
            "qty_cum": 0.0,
        })

    def _get_acceptance_prev_cum(self, period_no):
        self.ensure_one()
        prev = self.env["project.work.acceptance.progress"].search([
            ("assignment_id", "=", self.id),
            ("period_no", "<", period_no),
        ], order="period_no desc, id desc", limit=1)
        return prev.qty_cum if prev else 0.0

    @api.depends(
        "current_period_no",
        "acceptance_progress_ids.qty_cum",
        "acceptance_progress_ids.note",
        "acceptance_progress_ids.period_no",
    )
    def _compute_acceptance_current_values(self):
        for rec in self:
            if not rec.current_period_no:
                rec.prev_acceptance_qty_cum = 0.0
                rec.current_acceptance_qty_cum = 0.0
                rec.current_acceptance_qty_period = 0.0
                rec.current_acceptance_qty_remaining = 0.0
                rec.current_acceptance_note = False
                continue

            prev_cum = rec._get_acceptance_prev_cum(rec.current_period_no)
            current = rec.env["project.work.acceptance.progress"].search([
                ("assignment_id", "=", rec.id),
                ("period_no", "=", rec.current_period_no),
            ], limit=1)

            curr_cum = current.qty_cum if current else prev_cum
            rec.prev_acceptance_qty_cum = prev_cum
            rec.current_acceptance_qty_cum = curr_cum
            rec.current_acceptance_qty_period = max(0.0, (curr_cum or 0.0) - (prev_cum or 0.0))
            rec.current_acceptance_qty_remaining = max(0.0, (rec.qty_settlement or 0.0) - curr_cum)   
            rec.current_acceptance_note = current.note if current else False

    def _inverse_current_acceptance_qty_period(self):
        for rec in self:
            if not rec.current_period_no or not rec.current_period_start:
                continue
            progress = rec._get_or_create_acceptance_progress(rec.current_period_no)
            prev_cum = rec._get_acceptance_prev_cum(rec.current_period_no)
            new_cum = (prev_cum or 0.0) + (rec.current_acceptance_qty_period or 0.0)
            progress.write({"qty_cum": new_cum})

    def _inverse_current_acceptance_note(self):
        for rec in self:
            if not rec.current_period_no or not rec.current_period_start:
                continue
            progress = rec._get_or_create_acceptance_progress(rec.current_period_no)
            progress.write({"note": rec.current_acceptance_note or False})

    @api.depends("current_acceptance_qty_period", "current_acceptance_qty_cum", "work_item_id",)
    def _compute_acceptance_amounts(self):
        for rec in self:
            pu = rec.price_unit or 0.0
            rec.acceptance_value_current_period = (rec.current_acceptance_qty_period or 0.0) * pu
            rec.acceptance_value_cum = (rec.current_acceptance_qty_cum or 0.0) * pu
            rec.acceptance_value_prev_period = (rec.prev_acceptance_qty_cum or 0.0) * pu
            rec.current_acceptance_value_remaining = max(0.0, ((rec.qty_settlement or 0.0) - (rec.current_acceptance_qty_cum or 0.0)) * pu)
            rec.acceptance_process_percent = ((rec.current_acceptance_qty_cum or 0.0) / (rec.qty_done or 0.0) * 100.0) if rec.qty_done else 0.0

    # -------------------------
    # Công cụ sửa dữ liệu lỗi (manager)
    # -------------------------
    def action_repair_acceptance_cumulative(self):
        for rec in self:
            lines = rec.acceptance_progress_ids.sorted(key=lambda x: (x.period_no, x.id))
            running = 0.0
            for ln in lines:
                if (ln.qty_cum or 0.0) < running:
                    ln.qty_cum = running
                running = max(running, ln.qty_cum or 0.0)
        return True

    def action_fill_acceptance_user_manual_notice(self):
        raise UserError(
            "Vui lòng phân công 'Người báo cáo nghiệm thu' thủ công (không tự động suy ra)."
        )
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("acceptance_user_id") and vals.get("work_item_id"):
                wi = self.env["project.work.item"].browse(vals["work_item_id"])
                if wi.exists() and wi.acceptance_user_id:
                    vals["acceptance_user_id"] = wi.acceptance_user_id.id
        return super().create(vals_list)