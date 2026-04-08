from datetime import datetime
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

class ProposalSheet(models.Model):
    _inherit = "proposal.sheet"

    # ĐỔI: từ One2many -> Many2many vì 1 PO giờ có thể thuộc nhiều phiếu đề xuất
    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "proposal_sheet_purchase_rel",
        "proposal_sheet_id",
        "purchase_id",
        string="Đơn mua hàng",
    )
    purchase_order_count = fields.Integer(
        string="Số PO", compute="_compute_purchase_order_count"
    )

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    def action_view_purchase_orders(self):
        """
        Mở danh sách PO liên quan.
        - Nếu chọn nhiều phiếu đề xuất: hiện tất cả PO của tất cả phiếu.
        - Nếu chỉ có đúng 1 PO -> mở form luôn.
        """
        domain = [("proposal_sheet_ids", "in", self.ids)]
        # gom tất cả các PO có liên quan
        pos = self.env["purchase.order"].search(domain)

        action = {
            "type": "ir.actions.act_window",
            "name": _("Đơn mua hàng"),
            "res_model": "purchase.order",
            "view_mode": "tree,form",
            "domain": [("id", "in", pos.ids)],
            "context": {
                # context mặc định khi tạo PO thủ công từ đây
                "default_proposal_sheet_ids": [(6, 0, self.ids)],
            },
            "target": "current",
        }
        if len(pos) == 1:
            action.update({
                "view_mode": "form",
                "res_id": pos.id,
            })
        return action


    def action_create_purchase_orders(self):
        """
        Multi: tạo PO gộp từ nhiều Phiếu Đề Xuất.

        Điều kiện được phép:
        - Tất cả phiếu đều type = 'material'
        - Tất cả phiếu đều state thuộc nhóm cho phép
        - Tất cả phiếu cùng project
        - Tất cả phiếu cùng currency

        Kết quả:
        - Gộp theo vendor -> mỗi vendor 1 PO
        - Mỗi PO chỉ link những phiếu nào thực sự có dòng mua cho vendor đó

        Logic dòng:
        - Nếu line.product_id có giá trị -> dùng product_id
        - Ngược lại, dùng material_id.product_id
        - Nếu cả 2 đều không có -> tạo product tạm từ material_id
        - Đơn vị tính trên PO lấy theo đơn vị trên Phiếu Đề Xuất
        - Nếu đơn vị sản phẩm khác đơn vị trên Phiếu Đề Xuất thì tự động cập nhật sản phẩm theo đơn vị trên Phiếu Đề Xuất
        """
        if not self:
            raise UserError(_("Không có phiếu đề xuất nào được chọn."))

        # 1. Kiểm tra loại phiếu
        bad_type = self.filtered(lambda s: s.type != "material")
        if bad_type:
            raise ValidationError(_("Chỉ tạo Đơn mua cho Phiếu Đề Xuất loại 'Vật Tư'."))

        # 2. Kiểm tra trạng thái phiếu
        allowed_states = [
            "reviewed_accounting",
            "approved",
            "waiting_accounting_paid",
        ]
        bad_state = self.filtered(lambda s: s.state not in allowed_states)
        if bad_state:
            raise ValidationError(_(
                "Chỉ tạo Đơn mua cho Phiếu Đề Xuất ở các trạng thái: "
                "'KTTH Đang kiểm tra', 'Sếp Đang duyệt', hoặc 'Chờ KT xử lý'."
            ))

        # 3. Kiểm tra cùng dự án
        projects = self.mapped("project_id")
        if len(projects) > 1:
            raise ValidationError(_("Các Phiếu Đề Xuất phải thuộc cùng một Dự án."))
        common_project = projects[0] if projects else False

        # Nếu tất cả cùng một task -> gán task, nếu khác nhau -> bỏ trống
        tasks = self.mapped("task_id")
        common_task = tasks[0] if len(tasks) == 1 else False

        # 4. Kiểm tra cùng loại tiền tệ
        currencies = self.mapped("currency_id")
        if len(currencies) > 1:
            raise ValidationError(_("Các Phiếu Đề Xuất phải cùng loại tiền tệ."))
        common_currency = currencies[0] if currencies else self.env.company.currency_id

        # 5. Gom theo vendor
        vendor_groups = {}
        for sheet in self:
            for line in sheet.material_line_ids:
                qty = line.quantity or 0.0
                if qty <= 0:
                    continue

                if not line.vendor_id:
                    label = (
                        (line.product_id and line.product_id.display_name)
                        or (line.material_id and line.material_id.display_name)
                        or (line.description or "/")
                    )
                    raise ValidationError(
                        _("Dòng vật tư '%s' trong phiếu %s chưa có Nhà cung cấp.")
                        % (label, sheet.name)
                    )

                if not line.unit:
                    label = (
                        (line.product_id and line.product_id.display_name)
                        or (line.material_id and line.material_id.display_name)
                        or (line.description or "/")
                    )
                    raise ValidationError(
                        _("Dòng vật tư '%s' trong phiếu %s chưa có đơn vị tính.")
                        % (label, sheet.name)
                    )

                vendor = line.vendor_id
                bucket = vendor_groups.setdefault(vendor, {"lines": [], "sheet_ids": set()})
                bucket["lines"].append(line)
                bucket["sheet_ids"].add(sheet.id)

        if not vendor_groups:
            raise ValidationError(_("Không có dòng vật tư hợp lệ để tạo Đơn mua hàng."))

        created_pos = self.env["purchase.order"]
        all_origin_names = ", ".join(self.mapped("name"))

        # 6. Tạo PO cho từng vendor
        for vendor, data in vendor_groups.items():
            vendor_lines = data["lines"]
            sheets_for_vendor = self.browse(list(data["sheet_ids"]))

            # Gộp line theo (product_id, uom_id, price_unit, name)
            consolidated = {}

            for l in vendor_lines:
                # --- Xác định product ---
                product = (
                    l.product_id
                    or (l.material_id and getattr(l.material_id, "product_id", False))
                    or False
                )

                proposal_uom = l.unit
                if not proposal_uom:
                    label = (
                        l.description
                        or (l.product_id and l.product_id.display_name)
                        or (l.material_id and l.material_id.display_name)
                        or "/"
                    )
                    raise ValidationError(
                        _("Dòng vật tư '%s' chưa có đơn vị tính trên Phiếu Đề Xuất.") % label
                    )

                # Nếu chưa có product -> tạo product tạm theo đơn vị của phiếu đề xuất
                if not product and l.material_id:
                    product = self.env["product.product"].create({
                        "name": l.material_id.display_name,
                        "type": "service",
                        "uom_id": proposal_uom.id,
                        "uom_po_id": proposal_uom.id,
                        "purchase_ok": True,
                        "sale_ok": False,
                    })

                if not product:
                    label = l.description or "/"
                    raise ValidationError(
                        _("Không xác định được Sản phẩm cho dòng vật tư '%s'.") % label
                    )

                # --- Nếu đơn vị sản phẩm khác đơn vị phiếu đề xuất thì tự cập nhật sản phẩm ---
                product_tmpl = product.product_tmpl_id
                product_uom = product.uom_id
                product_po_uom = product.uom_po_id

                need_update_uom = (
                    not product_uom
                    or product_uom.id != proposal_uom.id
                    or not product_po_uom
                    or product_po_uom.id != proposal_uom.id
                )

                if need_update_uom:
                    # Cập nhật cả đơn vị gốc và đơn vị mua
                    # theo đúng đơn vị trên phiếu đề xuất
                    product_tmpl.write({
                        "uom_id": proposal_uom.id,
                        "uom_po_id": proposal_uom.id,
                    })

                    # refresh lại record sau khi write
                    product.invalidate_recordset(["uom_id", "uom_po_id"])
                    product_tmpl.invalidate_recordset(["uom_id", "uom_po_id"])

                # --- Dùng đơn vị từ phiếu đề xuất ---
                uom = proposal_uom

                # --- Thông tin dòng PO ---
                line_name = (
                    l.description
                    or product.display_name
                    or (l.material_id and l.material_id.display_name)
                    or "/"
                )
                unit_price = float(l.price_unit or 0.0)
                qty = l.quantity or 0.0

                key = (product.id, uom.id, unit_price, line_name)
                consolidated[key] = consolidated.get(key, 0.0) + qty

            order_lines_vals = []
            for (product_id, uom_id, unit_price, line_name), qty_total in consolidated.items():
                order_lines_vals.append((0, 0, {
                    "name": line_name,
                    "product_id": product_id,
                    "product_qty": qty_total,
                    "product_uom": uom_id,
                    "price_unit": unit_price,
                    "date_planned": fields.Datetime.now(),
                }))

            main_sheet = sheets_for_vendor[:1] or self[:1]

            po_vals = {
                "partner_id": vendor.id,
                "currency_id": common_currency.id,
                "company_id": self.env.company.id,
                "origin": all_origin_names,

                "proposal_sheet_ids": [(6, 0, sheets_for_vendor.ids)],
                "proposal_sheet_id": main_sheet.id,

                "project_id": common_project.id if common_project else False,
                "task_id": common_task.id if common_task else False,

                "order_line": order_lines_vals,
            }

            po = self.env["purchase.order"].create(po_vals)
            created_pos |= po

            for sheet in sheets_for_vendor:
                sheet.message_post(
                    body=_("Đã tạo Đơn mua hàng %s cho NCC %s từ phiếu %s.")
                    % (po.name, vendor.display_name, sheet.name)
                )

        # 7. Sau khi tạo PO: nếu có hàm đẩy stage task thì gọi
        for sheet in self:
            if hasattr(sheet, "_push_task_to_purchase_stage"):
                sheet._push_task_to_purchase_stage()

        # 8. Trả action mở danh sách PO vừa tạo
        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["domain"] = [("id", "in", created_pos.ids)]
        if len(created_pos) == 1:
            action.update({
                "view_mode": "form",
                "res_id": created_pos.id,
            })
        return action