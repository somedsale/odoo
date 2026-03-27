# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ProjectWorkItem(models.Model):
    _name = "project.work.item"
    _description = "Project Work Item"
    _order = "sequence, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    project_id = fields.Many2one(
        "project.project",
        required=True,
        ondelete="cascade",
        string="Dự án",
        index=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        related="project_id.company_id",
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        related="project_id.company_id.currency_id",
        store=True,
        readonly=True,
    )

    sequence = fields.Integer(default=10, tracking=True)
    active = fields.Boolean(default=True)

    name = fields.Char(string="Tên hạng mục", required=True, tracking=True)
    section_name = fields.Char(string="Danh mục")
    description = fields.Text(string="Mô tả")

    so_line_id = fields.Many2one(
        "sale.order.line",
        string="Dòng SO",
        readonly=True,
        index=True,
    )

    product_id = fields.Many2one(
        "product.product",
        string="Sản phẩm",
        required=True,
        tracking=True,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Đơn vị tính",
        required=True,
    )

    assigned_user_id = fields.Many2one(
        "res.users",
        string="Người báo cáo sản lượng",
        tracking=True,
    )
    assignment_ids = fields.One2many(
        "project.work.assignment",
        "work_item_id",
        string="Phân công",
    )

    progress_line_ids = fields.One2many(
        "project.work.progress",
        "work_item_id",
        string="Lịch sử lũy kế",
    )

    attachment_ids = fields.Many2many(
        "ir.attachment",
        related="project_id.attachment_ids",
        string="Tài liệu đính kèm",
        readonly=True,
    )

    # =========================================================
    # KHỐI LƯỢNG
    # =========================================================
    qty_plan = fields.Float(
        string="Khối lượng theo HĐ",
        digits="Product Unit of Measure",
        default=0.0,
        tracking=True,
    )
    qty_arise = fields.Float(
        string="Khối lượng phát sinh",
        digits="Product Unit of Measure",
        default=0.0,
        tracking=True,
    )
    qty_settlement = fields.Float(
        string="Khối lượng quyết toán / thực tế",
        compute="_compute_qty_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_done = fields.Float(
        string="Sản lượng đã thực hiện",
        compute="_compute_qty_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    qty_remaining = fields.Float(
        string="Khối lượng còn lại",
        compute="_compute_qty_metrics",
        store=True,
        digits="Product Unit of Measure",
    )
    progress_percent = fields.Float(
        string="Tỉ lệ hoàn thành (%)",
        compute="_compute_qty_metrics",
        store=True,
    )

    # =========================================================
    # ĐƠN GIÁ / GIÁ TRỊ TRƯỚC THUẾ
    # =========================================================
    price_unit = fields.Float(
        string="Đơn giá chưa thuế",
        related="so_line_id.price_unit",
        digits="Product Price",
        readonly=True,
        store=True,
    )
    price_subtotal = fields.Monetary(
        string="Thành tiền SO chưa thuế",
        related="so_line_id.price_subtotal",
        store=True,
        readonly=True,
    )

    value_plan = fields.Monetary(
        string="Giá trị KH theo HĐ",
        compute="_compute_value_metrics",
        store=True,
    )
    value_arise = fields.Monetary(
        string="Giá trị phát sinh",
        compute="_compute_value_metrics",
        store=True,
    )
    value_settlement = fields.Monetary(
        string="Giá trị quyết toán / thực tế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_completed = fields.Monetary(
        string="Giá trị hoàn thành",
        compute="_compute_value_metrics",
        store=True,
    )
    value_remaining = fields.Monetary(
        string="Giá trị còn lại",
        compute="_compute_value_metrics",
        store=True,
    )

    # =========================================================
    # ĐƠN GIÁ / GIÁ TRỊ SAU THUẾ
    # =========================================================
    price_unit_tax = fields.Monetary(
        string="Đơn giá sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_plan_tax = fields.Monetary(
        string="Giá trị KH theo HĐ sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_arise_tax = fields.Monetary(
        string="Giá trị phát sinh sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_settlement_tax = fields.Monetary(
        string="Giá trị quyết toán / thực tế sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_done_tax = fields.Monetary(
        string="Giá trị đã thực hiện sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )
    value_remaining_tax = fields.Monetary(
        string="Giá trị còn lại sau thuế",
        compute="_compute_value_metrics",
        store=True,
    )

    # =========================================================
    # COMPUTE HELPERS
    # =========================================================
    def _get_tax_included_amount(self, quantity, price_unit=None):
        self.ensure_one()

        quantity = quantity or 0.0
        if quantity <= 0:
            return 0.0

        price_unit = price_unit if price_unit is not None else (self.price_unit or 0.0)
        so_line = self.so_line_id
        if not so_line:
            return quantity * price_unit

        taxes = so_line.tax_id
        if not taxes:
            return quantity * price_unit

        currency = self.currency_id or self.env.company.currency_id
        partner = self.project_id.partner_id
        product = self.product_id

        tax_res = taxes.compute_all(
            price_unit,
            currency=currency,
            quantity=quantity,
            product=product,
            partner=partner,
        )
        return tax_res.get("total_included", quantity * price_unit)

    # =========================================================
    # COMPUTE: KHỐI LƯỢNG
    # =========================================================
    @api.depends(
        "qty_plan",
        "qty_arise",
        "assignment_ids.qty_done",
        "assignment_ids.active",
    )
    def _compute_qty_metrics(self):
        for rec in self:
            qty_plan = rec.qty_plan or 0.0
            qty_arise = rec.qty_arise or 0.0
            qty_settlement = qty_plan + qty_arise

            done = sum(
                rec.assignment_ids.filtered(lambda a: a.active).mapped("qty_done") or [0.0]
            )
            if done < 0:
                done = 0.0

            qty_remaining = qty_settlement - done
            if qty_remaining < 0:
                qty_remaining = 0.0

            rec.qty_settlement = qty_settlement
            rec.qty_done = done
            rec.qty_remaining = qty_remaining
            rec.progress_percent = (done / qty_settlement * 100.0) if qty_settlement else 0.0

    # =========================================================
    # COMPUTE: GIÁ TRỊ
    # =========================================================
    @api.depends(
        "price_unit",
        "so_line_id.tax_id",
        "qty_plan",
        "qty_arise",
        "qty_settlement",
        "qty_done",
        "qty_remaining",
        "project_id.partner_id",
        "project_id.currency_id",
        "product_id",
    )
    def _compute_value_metrics(self):
        for rec in self:
            price_unit = rec.price_unit or 0.0

            # Giá trị trước thuế
            rec.value_plan = (rec.qty_plan or 0.0) * price_unit
            rec.value_arise = (rec.qty_arise or 0.0) * price_unit
            
            # SỬA LOGIC: giá trị thực tế = giá trị hợp đồng + giá trị phát sinh
            rec.value_settlement = rec.value_plan + rec.value_arise

            rec.value_completed = (rec.qty_done or 0.0) * price_unit
            rec.value_remaining = rec.value_settlement - rec.value_completed
            if rec.value_remaining < 0:
                rec.value_remaining = 0.0

            # Giá trị sau thuế
            rec.price_unit_tax = rec._get_tax_included_amount(1.0, price_unit=price_unit)
            rec.value_plan_tax = rec._get_tax_included_amount(rec.qty_plan, price_unit=price_unit)
            rec.value_arise_tax = rec._get_tax_included_amount(rec.qty_arise, price_unit=price_unit)

            # SỬA LOGIC: sau thuế cũng cộng từ 2 giá trị thành phần
            rec.value_settlement_tax = rec.value_plan_tax + rec.value_arise_tax

            rec.value_done_tax = rec._get_tax_included_amount(rec.qty_done, price_unit=price_unit)
            rec.value_remaining_tax = rec.value_settlement_tax - rec.value_done_tax
            if rec.value_remaining_tax < 0:
                rec.value_remaining_tax = 0.0

    # =========================================================
    # ONCHANGE
    # =========================================================
    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.uom_id = rec.product_id.uom_id

    # =========================================================
    # CRUD
    # =========================================================
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_assignments_from_assignees()
        return records

    def write(self, vals):
        need_sync = any(k in vals for k in ["assigned_user_id", "project_id", "active"])
        res = super().write(vals)
        if need_sync:
            self._sync_assignments_from_assignees()
        return res

    # =========================================================
    # ASSIGNMENT SYNC
    # =========================================================
    def _sync_assignments_from_assignees(self):
        """
        Đồng bộ assigned_user_id -> project.work.assignment

        Quy ước:
        - Mỗi work item chỉ giữ tối đa 1 assignment active
        - Nếu bỏ assigned_user_id hoặc work item inactive -> archive assignment active
        - Nếu đổi người -> update dòng active gần nhất hoặc tái sử dụng dòng inactive gần nhất
        """
        Assignment = self.env["project.work.assignment"].sudo().with_context(active_test=False)

        for wi in self:
            if not wi.id:
                continue

            all_assignments = Assignment.search(
                [("work_item_id", "=", wi.id)],
                order="id asc",
            )
            active_assignments = all_assignments.filtered(lambda a: a.active)

            _logger.info(
                "[SYNC_ASSIGN] WI=%s (%s), assigned_user_id=%s, active=%s, total=%s",
                wi.id,
                wi.name,
                wi.assigned_user_id.id if wi.assigned_user_id else False,
                len(active_assignments),
                len(all_assignments),
            )

            # Không có người phụ trách hoặc work item bị archive
            if not wi.assigned_user_id or not wi.active:
                if active_assignments:
                    active_assignments.write({"active": False})
                continue

            target_uid = wi.assigned_user_id.id

            # Đã có dòng active đúng user -> giữ 1 dòng
            target_active = active_assignments.filtered(lambda a: a.user_id.id == target_uid)
            if target_active:
                keep = target_active.sorted(key=lambda a: a.id)[-1]
                extra_active = active_assignments - keep
                if extra_active:
                    extra_active.write({"active": False})

                vals_keep = {}
                if keep.project_id.id != wi.project_id.id:
                    vals_keep["project_id"] = wi.project_id.id
                if keep.work_item_id.id != wi.id:
                    vals_keep["work_item_id"] = wi.id
                if vals_keep:
                    keep.write(vals_keep)
                continue

            # Có active nhưng sai user -> update dòng active mới nhất
            if active_assignments:
                current = active_assignments.sorted(key=lambda a: a.id)[-1]
                vals_update = {
                    "user_id": target_uid,
                    "project_id": wi.project_id.id,
                    "work_item_id": wi.id,
                    "active": True,
                }
                current.write(vals_update)

                extra_active = active_assignments - current
                if extra_active:
                    extra_active.write({"active": False})
                continue

            # Không có active -> tái sử dụng inactive gần nhất
            reusable = all_assignments.filtered(lambda a: not a.active)
            if reusable:
                current = reusable.sorted(key=lambda a: a.id)[-1]
                current.write({
                    "user_id": target_uid,
                    "project_id": wi.project_id.id,
                    "work_item_id": wi.id,
                    "active": True,
                })
                continue

            # Chưa có dòng nào -> tạo mới
            Assignment.create({
                "project_id": wi.project_id.id,
                "work_item_id": wi.id,
                "user_id": target_uid,
                "active": True,
            })