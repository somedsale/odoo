from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ProposalSheet(models.Model):
    _inherit = "proposal.sheet"

    purchase_order_ids = fields.One2many(
        "purchase.order", "proposal_sheet_id", string="Đơn mua hàng"
    )
    purchase_order_count = fields.Integer(
        string="Số PO", compute="_compute_purchase_order_count"
    )

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    def action_view_purchase_orders(self):
        """Mở các PO liên kết với phiếu hiện tại — không đụng tới ir.actions.act_window."""
        self.ensure_one()
        domain = [("proposal_sheet_id", "=", self.id)]
        action = {
            "type": "ir.actions.act_window",
            "name": _("Đơn mua hàng"),
            "res_model": "purchase.order",
            "view_mode": "tree,form",
            "domain": domain,
            "context": {"default_proposal_sheet_id": self.id},
            "target": "current",
        }
        if len(self.purchase_order_ids) == 1:
            action.update({"view_mode": "form", "res_id": self.purchase_order_ids.id})
        return action

    def action_create_purchase_orders(self):
        """(ĐÃ GOM THEO NCC) Tạo 1 PO cho mỗi Nhà cung cấp từ dòng vật tư."""
        self.ensure_one()
        confirm = bool(self.env.context.get("confirm"))

        if self.type != "material":
            raise ValidationError(_("Chỉ tạo PO cho phiếu loại 'Vật tư'."))
        if not self.material_line_ids:
            raise ValidationError(_("Phiếu vật tư phải có ít nhất 1 dòng vật tư."))
        if self.purchase_order_ids:
            raise UserError(_("Phiếu này đã có Đơn mua hàng. Xem smart button 'Đơn mua hàng'."))

        # Gom theo vendor
        grouped = {}
        missing_vendor = []
        for l in self.material_line_ids:
            if not l.vendor_id:
                missing_vendor.append(l)
                continue
            grouped.setdefault(l.vendor_id, []).append(l)

        if missing_vendor:
            names = ", ".join(l.material_id.display_name for l in missing_vendor)
            raise ValidationError(_("Các dòng sau thiếu Nhà cung cấp đề xuất:\n%s") % names)

        created_pos = self.env["purchase.order"]
        for vendor, lines in grouped.items():
            consolidated = {}  # (product_id, uom_id, price_unit, name) -> qty
            for l in lines:
                product = getattr(l.material_id, "product_id", False) and l.material_id.product_id or False
                if not product:
                    product = self.env["product.product"].create({
                        "name": l.material_id.display_name,
                        "type": "service",
                        "uom_id": l.unit.id,
                        "uom_po_id": l.unit.id,
                        "purchase_ok": True,
                        "sale_ok": False,
                    })
                name = l.material_id.display_name or (l.description or "/")
                key = (product.id, l.unit.id, float(l.price_unit or 0.0), name)
                consolidated[key] = (consolidated.get(key, 0.0) + (l.quantity or 0.0))

            order_lines = []
            for (product_id, uom_id, price_unit, name), qty in consolidated.items():
                order_lines.append((0, 0, {
                    "name": name,
                    "product_id": product_id,
                    "product_qty": qty,
                    "product_uom": uom_id,
                    "price_unit": price_unit,
                    "date_planned": fields.Datetime.now(),
                }))

            po = self.env["purchase.order"].create({
                "partner_id": vendor.id,
                "currency_id": self.currency_id.id,
                "company_id": self.env.company.id,
                "origin": self.name,
                "proposal_sheet_id": self.id,  # cần field M2o trên purchase.order
                "order_line": order_lines,
            })
            if confirm and hasattr(po, "button_confirm"):
                po.button_confirm()
            created_pos |= po

        self.message_post(body=_("Đã tạo %s PO (mỗi NCC 1 đơn) từ Phiếu Đề Xuất.") % len(created_pos))
        # SAU KHI tạo xong PO -> đẩy task sang “Mua Hàng”
        self._push_task_to_purchase_stage()
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["domain"] = [("id", "in", created_pos.ids)]
        if len(created_pos) == 1:
            action.update({"view_mode": "form", "res_id": created_pos.id})
        return action
    def _push_task_to_purchase_stage(self):
        """Đẩy task sang stage 'Mua Hàng' sau khi tạo PO từ phiếu đề xuất."""
        STAGE_XID = "contract_management.task_type_purchase"  # đổi nếu stage ở module khác
        for sheet in self:
            task = sheet.task_id
            if not task:
                continue
            stage = self.env.ref(STAGE_XID, raise_if_not_found=False)
            if not stage:
                # Không tìm thấy stage theo XMLID -> bỏ qua (tránh crash)
                continue

            project = task.project_id
            if project:
                # Đảm bảo stage này có link với project (M2M project_ids) để hiện trên Kanban project đó
                if project.id not in stage.project_ids.ids:
                    stage.sudo().write({"project_ids": [(4, project.id)]})

            # Gán stage cho task (nếu khác hiện tại)
            if task.stage_id != stage:
                task.sudo().write({"stage_id": stage.id})