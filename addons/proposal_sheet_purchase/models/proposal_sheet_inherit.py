# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class ProposalSheet(models.Model):
    _inherit = "proposal.sheet"

    purchase_order_ids = fields.Many2many(
        "purchase.order",
        "proposal_sheet_purchase_rel",
        "proposal_sheet_id",
        "purchase_id",
        string="Đơn mua hàng",
    )

    purchase_order_count = fields.Integer(
        string="Số PO",
        compute="_compute_purchase_order_count",
    )

    def _compute_purchase_order_count(self):
        for rec in self:
            rec.purchase_order_count = len(rec.purchase_order_ids)

    def action_view_purchase_orders(self):
        domain = [("proposal_sheet_ids", "in", self.ids)]
        pos = self.env["purchase.order"].search(domain)

        action = {
            "type": "ir.actions.act_window",
            "name": _("Đơn mua hàng"),
            "res_model": "purchase.order",
            "view_mode": "tree,form",
            "domain": [("id", "in", pos.ids)],
            "context": {
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

    def _get_purchase_source_lines(self):
        self.ensure_one()

        if self.type == "material":
            return self.material_line_ids

        if self.type == "commercial_purchase":
            if "commercial_material_line_ids" in self._fields:
                return self.commercial_material_line_ids

            return self.env["proposal.material.line"].search([
                ("sheet_id", "=", self.id),
                ("type", "=", "commercial_purchase"),
            ])

        return self.env["proposal.material.line"]

    def _get_purchase_line_label(self, line):
        return (
            (line.product_id and line.product_id.display_name)
            or (getattr(line, "material_id", False) and line.material_id.display_name)
            or (line.description or "/")
        )

    def _get_purchase_line_product(self, line):
        product = (
            line.product_id
            or (
                getattr(line, "material_id", False)
                and getattr(line.material_id, "product_id", False)
            )
            or False
        )

        if product:
            return product

        material = getattr(line, "material_id", False)
        proposal_uom = line.unit

        if material and proposal_uom:
            product = self.env["product.product"].create({
                "name": material.display_name,
                "type": "service",
                "uom_id": proposal_uom.id,
                "uom_po_id": proposal_uom.id,
                "purchase_ok": True,
                "sale_ok": False,
            })
            return product

        return False

    def _prepare_purchase_order_line_name(self, line, product):
        """
        Diễn giải dòng PO.

        Mua hàng thương mại:
        - Chỉ lấy diễn giải từ sale.order.line.name
        - Không nối ghi chú phiếu đề xuất vào diễn giải

        Vật tư:
        - Giữ logic cũ: description nếu có, không thì product/material
        """
        if line.sheet_id.type == "commercial_purchase":
            sale_line = getattr(line, "sale_order_line_id", False)
            return (
                sale_line.name
                if sale_line and sale_line.name
                else product.display_name
                or "/"
            )

        return (
            line.description
            or product.display_name
            or (
                getattr(line, "material_id", False)
                and line.material_id.display_name
            )
            or "/"
        )

    def _prepare_purchase_order_notes(self, sheets):
        """
        Đưa ghi chú chung của Phiếu đề xuất qua Ghi chú/Terms của Đơn mua.

        Field ghi chú phiếu đề xuất hiện tại: take_note
        """
        note_parts = []

        for sheet in sheets:
            note = getattr(sheet, "take_note", False)
            if note:
                note_parts.append(
                    "Phiếu đề xuất %s:\n%s" % (
                        sheet.name or "/",
                        note,
                    )
                )

        if not note_parts:
            return False

        return "Ghi chú từ phiếu đề xuất:\n\n%s" % "\n\n".join(note_parts)

    def _ensure_product_uom_matches_proposal_uom(self, product, proposal_uom):
        if not product or not proposal_uom:
            return

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
            product_tmpl.write({
                "uom_id": proposal_uom.id,
                "uom_po_id": proposal_uom.id,
            })

            product.invalidate_recordset(["uom_id", "uom_po_id"])
            product_tmpl.invalidate_recordset(["uom_id", "uom_po_id"])

    def action_create_purchase_orders(self):
        if not self:
            raise UserError(_("Không có phiếu đề xuất nào được chọn."))

        allowed_types = ("material", "commercial_purchase")

        bad_type = self.filtered(lambda s: s.type not in allowed_types)
        if bad_type:
            raise ValidationError(_(
                "Chỉ tạo Đơn mua cho Phiếu Đề Xuất loại "
                "'Vật Tư' hoặc 'Mua hàng thương mại'."
            ))

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

        projects = self.mapped("project_id")
        if len(projects) > 1:
            raise ValidationError(_("Các Phiếu Đề Xuất phải thuộc cùng một Dự án."))

        common_project = projects[0] if projects else False

        tasks = self.mapped("task_id")
        common_task = tasks[0] if len(tasks) == 1 else False

        currencies = self.mapped("currency_id")
        if len(currencies) > 1:
            raise ValidationError(_("Các Phiếu Đề Xuất phải cùng loại tiền tệ."))

        common_currency = currencies[0] if currencies else self.env.company.currency_id

        vendor_groups = {}

        for sheet in self:
            source_lines = sheet._get_purchase_source_lines()

            if not source_lines:
                if sheet.type == "commercial_purchase":
                    raise ValidationError(
                        _("Phiếu %s chưa có dòng mua hàng thương mại để tạo Đơn mua hàng.")
                        % sheet.name
                    )
                raise ValidationError(
                    _("Phiếu %s chưa có dòng vật tư để tạo Đơn mua hàng.")
                    % sheet.name
                )

            for line in source_lines:
                qty = line.quantity or 0.0
                if qty <= 0:
                    continue

                label = sheet._get_purchase_line_label(line)

                if not line.vendor_id:
                    raise ValidationError(
                        _("Dòng '%s' trong phiếu %s chưa có Nhà cung cấp.")
                        % (label, sheet.name)
                    )

                if not line.unit:
                    raise ValidationError(
                        _("Dòng '%s' trong phiếu %s chưa có đơn vị tính.")
                        % (label, sheet.name)
                    )

                vendor = line.vendor_id
                bucket = vendor_groups.setdefault(vendor, {
                    "lines": [],
                    "sheet_ids": set(),
                })
                bucket["lines"].append(line)
                bucket["sheet_ids"].add(sheet.id)

        if not vendor_groups:
            raise ValidationError(_("Không có dòng hợp lệ để tạo Đơn mua hàng."))

        created_pos = self.env["purchase.order"]
        all_origin_names = ", ".join(self.mapped("name"))

        for vendor, data in vendor_groups.items():
            vendor_lines = data["lines"]
            sheets_for_vendor = self.browse(list(data["sheet_ids"]))

            consolidated = {}

            for line in vendor_lines:
                proposal_uom = line.unit

                if not proposal_uom:
                    label = self._get_purchase_line_label(line)
                    raise ValidationError(
                        _("Dòng '%s' chưa có đơn vị tính trên Phiếu Đề Xuất.")
                        % label
                    )

                product = self._get_purchase_line_product(line)

                if not product:
                    label = self._get_purchase_line_label(line)
                    raise ValidationError(
                        _("Không xác định được Sản phẩm cho dòng '%s'.") % label
                    )

                self._ensure_product_uom_matches_proposal_uom(product, proposal_uom)

                uom = proposal_uom
                line_name = self._prepare_purchase_order_line_name(line, product)
                unit_price = float(line.price_unit or 0.0)
                qty = line.quantity or 0.0

                proposal_line_note = line.description or False

                key = (product.id, uom.id, unit_price, line_name, proposal_line_note)
                consolidated[key] = consolidated.get(key, 0.0) + qty

            order_lines_vals = []
            for (product_id, uom_id, unit_price, line_name, proposal_line_note), qty_total in consolidated.items():
                order_lines_vals.append((0, 0, {
                    "name": line_name,
                    "product_id": product_id,
                    "product_qty": qty_total,
                    "product_uom": uom_id,
                    "price_unit": unit_price,
                    "date_planned": fields.Datetime.now(),
                    "proposal_line_note": proposal_line_note,
                }))

            main_sheet = sheets_for_vendor[:1] or self[:1]
            po_notes = self._prepare_purchase_order_notes(sheets_for_vendor)

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

            if po_notes:
                po_vals["notes"] = po_notes

            po = self.env["purchase.order"].create(po_vals)
            created_pos |= po

            for sheet in sheets_for_vendor:
                sheet.message_post(
                    body=_("Đã tạo Đơn mua hàng %s cho NCC %s từ phiếu %s.")
                    % (po.name, vendor.display_name, sheet.name)
                )

        for sheet in self:
            if hasattr(sheet, "_push_task_to_purchase_stage"):
                sheet._push_task_to_purchase_stage()

        action = self.env.ref("purchase.purchase_form_action").sudo().read()[0]
        action["domain"] = [("id", "in", created_pos.ids)]

        if len(created_pos) == 1:
            action.update({
                "view_mode": "form",
                "res_id": created_pos.id,
            })

        return action