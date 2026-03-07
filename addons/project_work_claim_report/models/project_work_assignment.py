# -*- coding: utf-8 -*-
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProjectWorkAssignment(models.Model):
    _inherit = "project.work.assignment"

    # =========================
    # Người báo cáo thanh/quyết toán (KHÁC người thi công)
    # =========================
    claim_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo thanh/QT",
        tracking=True,
        help="Người phụ trách báo cáo thanh/quyết toán cho phân công này.",
    )

    # =========================
    # Người thi công (lấy từ hạng mục công việc)
    # -> project.work.item.assigned_user_id
    # =========================
    executor_user_ids = fields.Many2one(
        "res.users",
        string="Người thi công",
        related="work_item_id.assigned_user_id",
        readonly=True,
        store=False,  # chỉ hiển thị, không cần SQL
    )

    # =========================
    # Lịch sử thanh/quyết toán theo kỳ
    # =========================
    claim_progress_ids = fields.One2many(
        "project.work.claim.progress",
        "assignment_id",
        string="Lịch sử thanh/quyết toán theo kỳ",
    )

    # =========================
    # Thông tin hiển thị (dùng cho view report)
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
        store=False,  # nếu muốn dùng searchpanel/group_by thì đổi store=True
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
        compute="_compute_claim_display_values",
        readonly=True,
        store=False,
    )
    price_unit = fields.Float(
        string="Đơn giá hạng mục",
        compute="_compute_claim_display_values",
        readonly=True,
        store=False,
    )

    # =========================
    # Kỳ hiện tại (dùng chung logic với báo cáo sản lượng)
    # =========================
    current_period_no = fields.Integer(
        string="Kỳ hiện tại",
        compute="_compute_claim_current_period",
        readonly=True,
        store=False,
    )
    current_period_start = fields.Date(
        string="Từ ngày",
        compute="_compute_claim_current_period",
        readonly=True,
        store=False,
    )
    current_period_end = fields.Date(
        string="Đến ngày",
        compute="_compute_claim_current_period",
        readonly=True,
        store=False,
    )

    # =========================
    # Nhập liệu thanh/quyết toán kỳ hiện tại
    # =========================
    prev_claim_qty_cum = fields.Float(
        string="Lũy kế thanh/QT kỳ trước",
        compute="_compute_claim_current_values",
        readonly=True,
        store=False,
        digits="Product Unit of Measure",
    )
    current_claim_qty_cum = fields.Float(
        string="Lũy kế thanh/QT hiện tại",
        compute="_compute_claim_current_values",
        readonly=True,
        store=False,
        digits="Product Unit of Measure",
    )
    current_claim_qty_remaining = fields.Float(
        string="KL thanh/QT còn lại",
        compute="_compute_claim_current_values",
        readonly=True,        store=False,
        digits="Product Unit of Measure",
    )
    current_claim_qty_period = fields.Float(
        string="Khối lượng thanh/QT trong kỳ",
        compute="_compute_claim_current_values",
        inverse="_inverse_current_claim_qty_period",
        store=False,
        digits="Product Unit of Measure",
    )
    current_claim_note = fields.Text(
        string="Ghi chú thanh/QT kỳ hiện tại",
        compute="_compute_claim_current_values",
        inverse="_inverse_current_claim_note",
        store=False,
    )

    claim_value_current_period = fields.Float(
        string="Giá trị thanh/QT kỳ này",
        compute="_compute_claim_amounts",
        readonly=True,
        store=False,
    )
    prev_claim_value_cum = fields.Float(
        string="Lũy kế giá trị thanh/QT kỳ trước",
        compute="_compute_claim_amounts",
        readonly=True,        store=False,
    )
    claim_value_current_remaining = fields.Float(
        string="Giá trị thanh/QT còn lại",
        compute="_compute_claim_amounts",
        readonly=True,
        store=False,    )
    claim_value_cum = fields.Float(
        string="Lũy kế giá trị thanh/QT",
        compute="_compute_claim_amounts",
        readonly=True,
        store=False,
    )
    claim_process_percent = fields.Float(
        string="% Thanh/QT",
        compute="_compute_claim_amounts",
        readonly=True,
        store=False,    )
    # -------------------------
    # Create/Write
    # -------------------------
    @api.model_create_multi
    def create(self, vals_list):
        """
        KHÔNG tự động gán claim_user_id = user_id nữa,
        vì người báo cáo quyết toán là người khác với người thi công.
        (Nếu muốn, có thể lấy từ work_item_id.claim_user_id ở module khác)
        """
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        return res

    # -------------------------
    # Ràng buộc nghiệp vụ
    # -------------------------
    # @api.constrains("claim_user_id", "work_item_id")
    # def _check_claim_user_not_executor(self):
    #     """
    #     Người báo cáo quyết toán không được trùng với người thi công
    #     (bất kỳ user nào trong assigned_user_id của work item).
    #     """
    #     for rec in self:
    #         if rec.claim_user_id and rec.work_item_id and rec.work_item_id.assigned_user_id:
    #             if rec.claim_user_id == rec.work_item_id.assigned_user_id:
    #                 raise ValidationError(
    #                     "Người báo cáo thanh/QT phải khác người thi công của hạng mục công việc."
    #                 )

    # -------------------------
    # Helpers tính giá trị hiển thị
    # -------------------------
    @api.depends("work_item_id")
    def _compute_claim_display_values(self):
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
    # Helpers kỳ báo cáo
    # -------------------------
    def _claim_get_period_bounds_fallback(self, date_start, period_no):
        """
        Kỳ 1: từ ngày phân công -> T7 tuần đó
        Kỳ sau: T2 -> T7
        """
        start = fields.Date.to_date(date_start)
        if period_no == 1:
            weekday = start.weekday()  # Mon=0..Sun=6
            delta = max(0, 5 - weekday)  # đến T7
            ps = start
            pe = start + timedelta(days=delta)
        else:
            base_mon = start - timedelta(days=start.weekday())
            ps = base_mon + timedelta(weeks=period_no - 1)
            pe = ps + timedelta(days=5)
        return ps, pe

    def _claim_get_period_bounds(self, date_start, period_no):
        self.ensure_one()
        if hasattr(super(ProjectWorkAssignment, self), "_get_period_bounds"):
            try:
                return super(ProjectWorkAssignment, self)._get_period_bounds(date_start, period_no)
            except Exception:
                pass
        return self._claim_get_period_bounds_fallback(date_start, period_no)

    def _claim_compute_current_period_no_from_date(self, d):
        self.ensure_one()
        if not self.date_start or not d:
            return 0
        start = fields.Date.to_date(self.date_start)
        d = fields.Date.to_date(d)
        if d < start:
            return 0

        p1s, p1e = self._claim_get_period_bounds(start, 1)
        if p1s <= d <= p1e:
            return 1

        base_mon = start - timedelta(days=start.weekday())
        k2_start = base_mon + timedelta(weeks=1)
        if d < k2_start:
            return 1
        weeks = ((d - k2_start).days // 7)
        return 2 + max(0, weeks)

    @api.depends("date_start")
    def _compute_claim_current_period(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.date_start:
                rec.current_period_no = 0
                rec.current_period_start = False
                rec.current_period_end = False
                continue

            period_no = rec._claim_compute_current_period_no_from_date(today)
            rec.current_period_no = period_no

            if period_no:
                ps, pe = rec._claim_get_period_bounds(rec.date_start, period_no)
                rec.current_period_start = ps
                rec.current_period_end = pe
            else:
                rec.current_period_start = False
                rec.current_period_end = False

    # -------------------------
    # Helpers dữ liệu claim progress
    # -------------------------
    def _get_or_create_claim_progress(self, period_no):
        self.ensure_one()
        Progress = self.env["project.work.claim.progress"]
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

    def _get_claim_prev_cum(self, period_no):
        self.ensure_one()
        prev = self.env["project.work.claim.progress"].search([
            ("assignment_id", "=", self.id),
            ("period_no", "<", period_no),
        ], order="period_no desc, id desc", limit=1)
        return prev.qty_cum if prev else 0.0

    @api.depends(
        "current_period_no",
        "claim_progress_ids.qty_cum",
        "claim_progress_ids.note",
        "claim_progress_ids.period_no",
    )
    def _compute_claim_current_values(self):
        for rec in self:
            if not rec.current_period_no:
                rec.prev_claim_qty_cum = 0.0
                rec.current_claim_qty_cum = 0.0
                rec.current_claim_qty_period = 0.0
                rec.current_claim_qty_remaining = 0.0
                rec.current_claim_note = False
                continue

            prev_cum = rec._get_claim_prev_cum(rec.current_period_no)
            current = rec.env["project.work.claim.progress"].search([
                ("assignment_id", "=", rec.id),
                ("period_no", "=", rec.current_period_no),
            ], limit=1)

            curr_cum = current.qty_cum if current else prev_cum
            rec.prev_claim_qty_cum = prev_cum
            rec.current_claim_qty_cum = curr_cum
            rec.current_claim_qty_period = max(0.0, (curr_cum or 0.0) - (prev_cum or 0.0))
            rec.current_claim_qty_remaining = max(0.0, (rec.current_acceptance_qty_cum or 0.0) - curr_cum)
            rec.current_claim_note = current.note if current else False

    def _inverse_current_claim_qty_period(self):
        for rec in self:
            if not rec.current_period_no or not rec.current_period_start:
                continue
            progress = rec._get_or_create_claim_progress(rec.current_period_no)
            prev_cum = rec._get_claim_prev_cum(rec.current_period_no)
            new_cum = (prev_cum or 0.0) + (rec.current_claim_qty_period or 0.0)
            progress.write({"qty_cum": new_cum})

    def _inverse_current_claim_note(self):
        for rec in self:
            if not rec.current_period_no or not rec.current_period_start:
                continue
            progress = rec._get_or_create_claim_progress(rec.current_period_no)
            progress.write({"note": rec.current_claim_note or False})

    @api.depends("current_claim_qty_period", "current_claim_qty_cum", "work_item_id")
    def _compute_claim_amounts(self):
        for rec in self:
            pu = rec.price_unit or 0.0
            rec.prev_claim_value_cum = (rec.prev_claim_qty_cum or 0.0) * pu
            rec.claim_value_current_period = (rec.current_claim_qty_period or 0.0) * pu
            rec.claim_value_cum = (rec.current_claim_qty_cum or 0.0) * pu
            rec.claim_value_current_remaining = max(0.0, (rec.current_acceptance_qty_cum or 0.0) - (rec.current_claim_qty_cum or 0.0)) * pu
            rec.claim_process_percent = (rec.current_claim_qty_cum / rec.current_acceptance_qty_cum * 100.0) if rec.current_acceptance_qty_cum else 0.0

    # -------------------------
    # Công cụ sửa dữ liệu lỗi (manager)
    # -------------------------
    def action_repair_claim_cumulative(self):
        for rec in self:
            lines = rec.claim_progress_ids.sorted(key=lambda x: (x.period_no, x.id))
            running = 0.0
            for ln in lines:
                if (ln.qty_cum or 0.0) < running:
                    ln.qty_cum = running
                running = max(running, ln.qty_cum or 0.0)
        return True

    # -------------------------
    # Backfill claim_user cho dữ liệu cũ
    # -> KHÔNG lấy từ user_id nữa vì người thi công là assigned_user_id ở work item
    # -------------------------
    def action_fill_claim_user_from_assignee(self):
        raise UserError(
            "Không thể tự động suy ra 'Người báo cáo thanh/QT' từ 'Người thi công' "
            "vì người thi công nằm ở danh sách assigned_user_id của hạng mục. "
            "Vui lòng phân công người báo cáo thanh/QT thủ công."
        )