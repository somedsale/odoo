from odoo import api, fields, models, _
import logging

_logger = logging.getLogger(__name__)


class ProjectWorkItem(models.Model):
    _name = "project.work.item"
    _description = "Project Work Item"
    _order = "sequence, id"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    project_id = fields.Many2one("project.project", required=True, ondelete="cascade", string="Dự án", index=True)
    company_id = fields.Many2one(related="project_id.company_id", store=True, readonly=True)

    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    name = fields.Char(string="Tên hạng mục", required=True)
    so_line_id = fields.Many2one("sale.order.line", string="Dòng SO", readonly=True)

    product_id = fields.Many2one("product.product", string="Sản phẩm", required=True)
    uom_id = fields.Many2one("uom.uom", string="Đơn vị tính", required=True)
    description = fields.Text(string="Mô tả")
    qty_plan = fields.Float(string="Khối lượng theo HĐ", digits="Product Unit of Measure", default=0.0)
    qty_arise = fields.Float(string="Khối lượng phát sinh", digits="Product Unit of Measure", default=0.0)
    value_arise = fields.Monetary(string="Giá trị phát sinh", compute="_compute_qty_settlement", store=True)
    qty_settlement = fields.Float(string="Khối lượng thực tế", compute="_compute_qty_settlement", digits="Product Unit of Measure", default=0.0)
    value_settlement = fields.Monetary(string="Giá trị thực tế", compute="_compute_qty_settlement", store=True)
    assigned_user_id = fields.Many2one("res.users", string="Người báo cáo sản lượng")
    assignment_ids = fields.One2many("project.work.assignment", "work_item_id", string="Phân công")

    price_unit = fields.Float(string="Đơn giá", related="so_line_id.price_unit", digits="Product Price", readonly=True)
    price_subtotal = fields.Monetary(string="Thành tiền", related="so_line_id.price_subtotal", store=True)
    qty_done = fields.Float(string="Sản lượng đã đạt được", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    qty_remaining = fields.Float(string="Sản lượng còn lại", compute="_compute_qty_done", store=True, digits="Product Unit of Measure")
    progress_percent = fields.Float(string="Tỉ lệ hoàn thành", compute="_compute_qty_done", store=True)
    value_completed = fields.Monetary(string="Giá trị hoàn thành", compute="_compute_qty_done", store=True)
    value_remaining = fields.Monetary(string="Giá trị còn lại", compute="_compute_qty_done", store=True)
    currency_id = fields.Many2one(related="project_id.company_id.currency_id", store=True, readonly=True)

    progress_line_ids = fields.One2many("project.work.progress", "work_item_id", string="Lịch sử lũy kế")
    section_name = fields.Char(string="Danh mục")
    attachment_ids = fields.Many2many("ir.attachment", related="project_id.attachment_ids", string="Tài liệu đính kèm")
    @api.depends("qty_plan", "qty_arise", "price_unit", "qty_settlement")
    def _compute_qty_settlement(self):
        for rec in self:
            rec.qty_settlement = (rec.qty_plan or 0.0) + (rec.qty_arise or 0.0)
            rec.value_settlement = rec.qty_settlement * rec.price_unit if rec.price_unit else 0.0
            rec.value_arise = rec.qty_arise * rec.price_unit if rec.price_unit else 0.0

    @api.depends("qty_plan", "assignment_ids.qty_done", "assignment_ids.active", "price_unit", "qty_settlement","qty_arise")
    def _compute_qty_done(self):
        for rec in self:
            # chỉ cộng assignment active để tránh cộng dồn dữ liệu cũ
            done = sum(rec.assignment_ids.filtered(lambda a: a.active).mapped("qty_done") or [0.0])

            rec.qty_done = done
            qty_remaining = (rec.qty_settlement or 0.0) - done
            rec.qty_remaining = qty_remaining if qty_remaining > 0.0 else 0.0

            rec.progress_percent = ((done / rec.qty_settlement) * 100.0) if rec.qty_settlement else 0.0
            rec.value_completed = (done * rec.price_unit) if rec.price_unit else 0.0
            rec.value_remaining = rec.value_settlement - rec.value_completed if rec.value_settlement else 0.0

    @api.onchange("product_id")
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.uom_id = rec.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_assignments_from_assignees()
        return records

    def write(self, vals):
        # sync khi đổi người phụ trách hoặc đổi project (để assignment.project_id khớp)
        need_sync = any(k in vals for k in ["assigned_user_id", "project_id"])
        res = super().write(vals)
        if need_sync:
            self._sync_assignments_from_assignees()
        return res

    def _sync_assignments_from_assignees(self):
        """
        Đồng bộ assigned_user_id (Many2one) -> project.work.assignment
        Quy ước:
        - 1 work item chỉ giữ 1 assignment active (người phụ trách hiện tại)
        - bỏ assigned_user_id -> archive assignment active
        - đổi người -> update dòng active mới nhất hoặc tạo mới
        """
        Assignment = self.env["project.work.assignment"].sudo().with_context(active_test=False)

        for wi in self:
            # đảm bảo record đã có ID
            if not wi.id:
                continue

            # Lấy tất cả dòng assignment của work item (active + inactive)
            all_assignments = Assignment.search(
                [("work_item_id", "=", wi.id)],
                order="id asc"
            )
            active_assignments = all_assignments.filtered(lambda a: a.active)

            _logger.info(
                "[SYNC_ASSIGN] WI=%s (%s), assigned_user_id=%s, total=%s, active=%s",
                wi.id, wi.name, wi.assigned_user_id.id if wi.assigned_user_id else False,
                len(all_assignments), len(active_assignments)
            )

            # 0) Không có người phụ trách -> archive tất cả active
            if not wi.assigned_user_id:
                if active_assignments:
                    active_assignments.write({"active": False})
                continue

            target_uid = wi.assigned_user_id.id

            # 1) Đã có active đúng user -> giữ 1 dòng, archive dòng active dư
            target_active = active_assignments.filtered(lambda a: a.user_id.id == target_uid)
            if target_active:
                keep = target_active.sorted(key=lambda a: a.id)[-1]
                extra_active = active_assignments - keep
                if extra_active:
                    extra_active.write({"active": False})

                # đồng bộ project_id nếu lệch (phòng trường hợp đổi project)
                if keep.project_id.id != wi.project_id.id:
                    keep.write({"project_id": wi.project_id.id})
                continue

            # 2) Có active nhưng sai user -> update dòng active mới nhất
            if active_assignments:
                current = active_assignments.sorted(key=lambda a: a.id)[-1]
                vals_update = {
                    "user_id": target_uid,
                    "project_id": wi.project_id.id,
                    "active": True,
                }

                # optional field nếu model có
                if "claim_user_id" in current._fields and "claim_user_id" in wi._fields:
                    vals_update["claim_user_id"] = wi.claim_user_id.id or False

                current.write(vals_update)

                # archive các active dư
                extra_active = active_assignments - current
                if extra_active:
                    extra_active.write({"active": False})
                continue

            # 3) Không có active -> tái sử dụng 1 dòng inactive gần nhất (nếu có)
            reusable = all_assignments.filtered(lambda a: not a.active)
            if reusable:
                current = reusable.sorted(key=lambda a: a.id)[-1]
                vals_update = {
                    "project_id": wi.project_id.id,
                    "work_item_id": wi.id,
                    "user_id": target_uid,
                    "active": True,
                }

                if "claim_user_id" in current._fields and "claim_user_id" in wi._fields:
                    vals_update["claim_user_id"] = wi.claim_user_id.id or False

                current.write(vals_update)
                continue

            # 4) Chưa có dòng nào -> tạo mới
            vals_create = {
                "project_id": wi.project_id.id,
                "work_item_id": wi.id,
                "user_id": target_uid,
                "active": True,
            }

            if "claim_user_id" in Assignment._fields and "claim_user_id" in wi._fields:
                vals_create["claim_user_id"] = wi.claim_user_id.id or False

            Assignment.create(vals_create)