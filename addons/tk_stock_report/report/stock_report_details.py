# -*- coding: utf-8 -*-
from collections import defaultdict
import calendar

from odoo import models, api, fields


class StockReportDetails(models.AbstractModel):
    _name = "report.tk_stock_report.stock_report_template"
    _description = "Stock Summary Report"

    @api.model
    def _get_report_values(self, docids, data=None):
        data = data or {}
        form_data = data.get("form_data") or {}

        # --------- ĐỌC FILTER KỲ ----------
        start_date = form_data.get("start_date")
        end_date = form_data.get("end_date")
        period_type = form_data.get("period_type") or "custom"
        month = form_data.get("month")
        quarter = form_data.get("quarter")
        year = form_data.get("year")

        # Nếu thiếu start/end mà có filter kỳ thì tự tính
        if (not start_date or not end_date) and period_type != "custom":
            today = fields.Date.context_today(self)
            y = int(year) if year else today.year

            if period_type == "month" and month:
                m = int(month)
                last_day = calendar.monthrange(y, m)[1]
                start_date = f"{y:04d}-{m:02d}-01"
                end_date = f"{y:04d}-{m:02d}-{last_day:02d}"

            elif period_type == "quarter" and quarter:
                q = int(quarter)
                start_month = 3 * (q - 1) + 1
                end_month = start_month + 2
                last_day = calendar.monthrange(y, end_month)[1]
                start_date = f"{y:04d}-{start_month:02d}-01"
                end_date = f"{y:04d}-{end_month:02d}-{last_day:02d}"

            elif period_type == "year":
                start_date = f"{y:04d}-01-01"
                end_date = f"{y:04d}-12-31"

            form_data["start_date"] = start_date
            form_data["end_date"] = end_date

        # --------- PHẦN ĐỌC FILTER KHO / CÔNG TY ----------
        location_val = form_data.get("stock_location_id") or False
        company_val = form_data.get("company_id") or False

        location_id = location_val[0] if isinstance(location_val, (list, tuple)) else location_val
        company_id = company_val[0] if isinstance(company_val, (list, tuple)) else company_val

        if not company_id:
            company_id = self.env.company.id

        Location = self.env["stock.location"]
        Move = self.env["stock.move"].sudo()
        Product = self.env["product.product"]

        # Field số lượng trên move (tương thích nhiều version)
        qty_field = "quantity_done" if "quantity_done" in Move._fields else "product_uom_qty"

        # Kiểm tra xem move có custom field value_amount / unit_cost không
        has_value_amount = "value_amount" in Move._fields
        has_unit_cost = "unit_cost" in Move._fields

        # Lấy danh sách kho nội bộ
        location = Location.browse(location_id) if location_id else False
        if location:
            location_ids = Location.search([("id", "child_of", location.id)]).ids
        else:
            location_ids = Location.search(
                [("company_id", "=", company_id), ("usage", "=", "internal")]
            ).ids

        if not location_ids:
            return {
                "data": form_data,
                "lines": [],
                "totals": {},
                "company": self.env["res.company"].browse(company_id),
                "location": location,
            }

        # --------- LẤY MOVE TRƯỚC KỲ + TRONG KỲ ----------
        base_domain = [
            ("company_id", "=", company_id),
            ("state", "=", "done"),
            ("product_id.detailed_type", "=", "product"),
            "|",
            ("location_id", "in", location_ids),
            ("location_dest_id", "in", location_ids),
        ]

        moves_before = Move.search(base_domain + [("date", "<", start_date)])
        moves_period = Move.search(
            base_domain
            + [
                ("date", ">=", start_date),
                ("date", "<=", end_date),
            ],
            order="date ASC",
        )

        product_ids = set(
            moves_before.mapped("product_id").ids + moves_period.mapped("product_id").ids
        )

        lines = []
        totals = defaultdict(float)

        # --------- HÀM PHỤ TÍNH GIÁ TRỊ MOVE ----------
        def _compute_moves_value(moves, location_ids, incoming=True):
            """Tính tổng giá trị các move:
               - incoming=True: lấy move có location_dest_id in location_ids
               - incoming=False: lấy move có location_id in location_ids
               Ưu tiên dùng value_amount, nếu không có thì unit_cost * qty.
            """
            if incoming:
                mf = moves.filtered(lambda m, lids=location_ids: m.location_dest_id.id in lids)
            else:
                mf = moves.filtered(lambda m, lids=location_ids: m.location_id.id in lids)

            total_val = 0.0
            for m in mf:
                qty = getattr(m, qty_field, 0.0) or 0.0
                if has_value_amount and m.value_amount:
                    total_val += m.value_amount
                elif has_unit_cost and m.unit_cost:
                    total_val += m.unit_cost * qty
                else:
                    # Fallback cuối cùng: dùng standard_price nếu có
                    total_val += (m.product_id.standard_price or 0.0) * qty
            return total_val

        # --------- VÒNG LẶP THEO SẢN PHẨM ----------
        for product in Product.browse(product_ids):
            if not product.exists():
                continue

            mb = moves_before.filtered(lambda m, p=product: m.product_id.id == p.id)
            mp = moves_period.filtered(lambda m, p=product: m.product_id.id == p.id)

            # --- Số lượng đầu kỳ ---
            opening_in_qty = sum(
                mb.filtered(lambda m, lids=location_ids: m.location_dest_id.id in lids).mapped(qty_field)
            )
            opening_out_qty = sum(
                mb.filtered(lambda m, lids=location_ids: m.location_id.id in lids).mapped(qty_field)
            )
            opening_qty = opening_in_qty - opening_out_qty

            # --- Giá trị đầu kỳ ---
            opening_in_val = _compute_moves_value(mb, location_ids, incoming=True)
            opening_out_val = _compute_moves_value(mb, location_ids, incoming=False)
            opening_val = opening_in_val - opening_out_val

            # --- Số lượng nhập / xuất trong kỳ ---
            in_qty = sum(
                mp.filtered(lambda m, lids=location_ids: m.location_dest_id.id in lids).mapped(qty_field)
            )
            out_qty = sum(
                mp.filtered(lambda m, lids=location_ids: m.location_id.id in lids).mapped(qty_field)
            )

            # --- Giá trị nhập / xuất trong kỳ ---
            in_val = _compute_moves_value(mp, location_ids, incoming=True)
            out_val = _compute_moves_value(mp, location_ids, incoming=False)

            # --- Tồn cuối kỳ ---
            closing_qty = opening_qty + in_qty - out_qty
            closing_val = opening_val + in_val - out_val

            # 🔹 ĐƠN GIÁ BÌNH QUÂN (trọng số theo giá trị)
            opening_unit_cost = opening_val / opening_qty if opening_qty else 0.0
            in_unit_cost = in_val / in_qty if in_qty else 0.0      # <= GIÁ NHẬP BÌNH QUÂN
            out_unit_cost = out_val / out_qty if out_qty else 0.0
            closing_unit_cost = closing_val / closing_qty if closing_qty else 0.0

            # Bỏ qua sản phẩm hoàn toàn không phát sinh gì
            if not opening_qty and not in_qty and not out_qty and not closing_qty:
                continue

            line = {
                "default_code": product.default_code or "",
                "name": product.name or "",
                "uom": product.uom_id.name or "",
                "opening_qty": opening_qty,
                "opening_val": opening_val,
                "opening_unit_cost": opening_unit_cost,   # NEW

                "in_qty": in_qty,
                "in_val": in_val,
                "in_unit_cost": in_unit_cost,             # NEW → GIÁ NHẬP BÌNH QUÂN

                "out_qty": out_qty,
                "out_val": out_val,
                "out_unit_cost": out_unit_cost,           # NEW (nếu muốn xem)

                "closing_qty": closing_qty,
                "closing_val": closing_val,
                "closing_unit_cost": closing_unit_cost,   # NEW
            }
            lines.append(line)

            totals["opening_qty"] += opening_qty
            totals["opening_val"] += opening_val
            totals["in_qty"] += in_qty
            totals["in_val"] += in_val
            totals["out_qty"] += out_qty
            totals["out_val"] += out_val
            totals["closing_qty"] += closing_qty
            totals["closing_val"] += closing_val

        lines = sorted(lines, key=lambda l: (l["default_code"] or "", l["name"] or ""))

        return {
            "data": form_data,
            "lines": lines,
            "totals": totals,
            "company": self.env["res.company"].browse(company_id),
            "location": location,
        }
