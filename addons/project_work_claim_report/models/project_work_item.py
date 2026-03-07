# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ProjectWorkItem(models.Model):
    _inherit = "project.work.item"

    # Khối lượng quyết toán (lũy kế) tổng theo tất cả assignment của hạng mục
    claim_qty_done = fields.Float(
        string="KL quyết toán lũy kế",
        compute="_compute_claim_totals",
        digits="Product Unit of Measure",
        store=False,
    )
    claim_qty_remaining = fields.Float(
        string="KL quyết toán còn lại",
        compute="_compute_claim_totals",
        digits="Product Unit of Measure",
        store=False,
    )
    claim_progress_percent = fields.Float(
        string="% quyết toán",
        compute="_compute_claim_totals",
        store=False,
    )

    # Giá trị quyết toán
    claim_value_done = fields.Float(
        string="Giá trị quyết toán lũy kế",
        compute="_compute_claim_totals",
        store=False,
    )
    claim_value_remaining = fields.Float(
        string="Giá trị quyết toán còn lại",
        compute="_compute_claim_totals",
        store=False,
    )
    claim_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo thanh/QT",
        help="Người phụ trách báo cáo thanh/quyết toán cho phân công.",
    )
    def _get_price_unit_for_claim(self):
        """Ưu tiên price_unit, fallback price_subtotal/qty_plan."""
        self.ensure_one()
        if "price_unit" in self._fields:
            return self.price_unit or 0.0
        if "price_subtotal" in self._fields and (self.qty_plan or 0.0):
            return (self.price_subtotal or 0.0) / self.qty_plan if self.qty_plan else 0.0
        return 0.0

    @api.depends(
        "acceptance_qty_done",
        "assignment_ids.claim_progress_ids.qty_cum",
        "assignment_ids.claim_progress_ids.period_no",
    )
    def _compute_claim_totals(self):
        for rec in self:
            qty_claim_done = 0.0

            # Mỗi assignment lấy dòng claim_progress có period_no lớn nhất (lũy kế hiện tại)
            for assign in rec.assignment_ids:
                latest = False
                if assign.claim_progress_ids:
                    latest = assign.claim_progress_ids.sorted(
                        key=lambda x: (x.period_no or 0, x.id)
                    )[-1]
                qty_claim_done += (latest.qty_cum or 0.0) if latest else 0.0

            acceptance_qty_done = rec.acceptance_qty_done or 0.0
            qty_remaining = max(0.0, acceptance_qty_done - qty_claim_done)

            rec.claim_qty_done = qty_claim_done
            rec.claim_qty_remaining = qty_remaining
            rec.claim_progress_percent = (qty_claim_done / acceptance_qty_done * 100.0) if acceptance_qty_done else 0.0

            pu = rec._get_price_unit_for_claim()
            rec.claim_value_done = qty_claim_done * pu
            rec.claim_value_remaining = qty_remaining * pu
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)

        # Nếu tạo hạng mục đã có claim_user_id sẵn thì sync xuống assignment (nếu assignment đã tồn tại)
        for rec, vals in zip(records, vals_list):
            if vals.get("claim_user_id"):
                rec._sync_claim_user_to_assignments()
        return records

    def write(self, vals):
        # Chỉ xử lý khi có thay đổi claim_user_id
        sync_claim_user = "claim_user_id" in vals

        res = super().write(vals)

        if sync_claim_user:
            self._sync_claim_user_to_assignments()

        return res

    def _sync_claim_user_to_assignments(self):
        """
        Đồng bộ người quyết toán từ hạng mục xuống các phân công của hạng mục.
        - Nếu work item có nhiều assignment -> tất cả assignment cùng nhận claim_user_id này.
        - Nếu claim_user_id = False -> bỏ phân công người quyết toán ở assignment.
        """
        for rec in self:
            if not rec.assignment_ids:
                continue

            # Nếu muốn chỉ sync assignment đang active thì dùng filtered(lambda a: a.active)
            assignments = rec.assignment_ids
            assignments.write({
                "claim_user_id": rec.claim_user_id.id if rec.claim_user_id else False
            })