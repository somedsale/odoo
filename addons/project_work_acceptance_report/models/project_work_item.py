# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectWorkItem(models.Model):
    _inherit = "project.work.item"

    acceptance_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo nghiệm thu",
        tracking=True,
        help="Người phụ trách báo cáo nghiệm thu cho hạng mục công việc.",
    )
    acceptance_qty_done = fields.Float(
        string="KL nghiệm thu lũy kế",
        compute="_compute_acceptance_totals",
        digits="Product Unit of Measure",
        store=False,
    )
    acceptance_qty_remaining = fields.Float(
        string="KL nghiệm thu còn lại",
        compute="_compute_acceptance_totals",
        digits="Product Unit of Measure",
        store=False,
    )
    acceptance_progress_percent = fields.Float(
        string="% nghiệm thu",
        compute="_compute_acceptance_totals",
        store=False,
    )
    acceptance_value_done = fields.Float(
        string="Giá trị nghiệm thu lũy kế",
        compute="_compute_acceptance_totals",
        store=False,
    )
    acceptance_value_remaining = fields.Float(
        string="Giá trị nghiệm thu còn lại",
        compute="_compute_acceptance_totals",
        store=False,
    )

    def _get_price_unit_for_acceptance(self):
        self.ensure_one()
        if "price_unit" in self._fields:
            return self.price_unit or 0.0
        if "price_subtotal" in self._fields and (self.qty_settlement or 0.0):
            return (self.price_subtotal or 0.0) / self.qty_settlement if self.qty_settlement else 0.0
        return 0.0

    @api.depends(
        "qty_settlement",
        "assignment_ids.acceptance_progress_ids.qty_cum",
        "assignment_ids.acceptance_progress_ids.period_no",
    )
    def _compute_acceptance_totals(self):
        for rec in self:
            qty_done = 0.0
            for assign in rec.assignment_ids:
                latest = False
                if assign.acceptance_progress_ids:
                    latest = assign.acceptance_progress_ids.sorted(key=lambda x: (x.period_no or 0, x.id))[-1]
                qty_done += (latest.qty_cum or 0.0) if latest else 0.0

            qty_settlement = rec.qty_settlement or 0.0
            qty_remaining = max(0.0, qty_settlement - qty_done)

            rec.acceptance_qty_done = qty_done
            rec.acceptance_qty_remaining = qty_remaining
            rec.acceptance_progress_percent = (qty_done / qty_settlement * 100.0) if qty_settlement else 0.0

            pu = rec._get_price_unit_for_acceptance()
            rec.acceptance_value_done = qty_done * pu
            rec.acceptance_value_remaining = qty_remaining * pu
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Nếu tạo hạng mục đã có acceptance_user_id sẵn thì sync xuống assignment (nếu assignment đã tồn tại)
        for rec, vals in zip(records, vals_list):
            if "acceptance_user_id" in vals:
                rec._sync_acceptance_user_to_assignments()
        return records

    def write(self, vals):
        # Chỉ xử lý khi có thay đổi acceptance_user_id
        sync_acceptance_user = "acceptance_user_id" in vals

        res = super().write(vals)

        if sync_acceptance_user:
            self._sync_acceptance_user_to_assignments()

        return res

    def _sync_acceptance_user_to_assignments(self):
        """
        Đồng bộ người báo cáo nghiệm thu từ hạng mục xuống các phân công của hạng mục.
        - Nếu work item có nhiều assignment -> tất cả assignment cùng nhận acceptance_user_id này.
        - Nếu acceptance_user_id = False -> bỏ phân công người nghiệm thu ở assignment.
        """
        for rec in self:
            if not rec.assignment_ids:
                continue

            # Nếu muốn chỉ sync assignment đang active thì dùng filtered(lambda a: a.active)
            assignments = rec.assignment_ids
            assignments.write({
                "acceptance_user_id": rec.acceptance_user_id.id if rec.acceptance_user_id else False
            })