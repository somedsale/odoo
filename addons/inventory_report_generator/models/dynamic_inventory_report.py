# -*- coding: utf-8 -*-
import io
import json
import calendar
from collections import defaultdict
from datetime import date, datetime, time

from odoo import api, fields, models

try:
    from odoo.tools.misc import xlsxwriter
except ImportError:
    import xlsxwriter


class DynamicInventoryReport(models.Model):
    _name = "dynamic.inventory.report"
    _description = "Inventory Movement Summary (by period & location)"

    period_type = fields.Selection(
        [
            ("custom", "Custom Range"),
            ("month", "Month"),
            ("quarter", "Quarter"),
            ("year", "Year"),
        ],
        string="Period Type",
        default="custom",
        required=True,
    )

    date_from = fields.Date(string="Date From")
    date_to = fields.Date(string="Date To")

    # ✅ selection key là string (đừng dùng Integer)
    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Month")
    quarter = fields.Selection([("1", "Q1"), ("2", "Q2"), ("3", "Q3"), ("4", "Q4")], string="Quarter")
    year = fields.Integer(string="Year", default=lambda self: fields.Date.context_today(self).year)

    location_id = fields.Many2one("stock.location", string="Location")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    # -----------------
    # Helpers
    # -----------------

    def _compute_date_range(self, rec):
        """Return (start_date, end_date) as python date objects."""
        today = fields.Date.context_today(self)
        y = int(rec.year or today.year)

        if rec.period_type == "custom":
            dfrom = rec.date_from or today
            dto = rec.date_to or today
            if dto < dfrom:
                dfrom, dto = dto, dfrom
            return dfrom, dto

        if rec.period_type == "month":
            m = int(rec.month or today.month)
            last_day = calendar.monthrange(y, m)[1]
            return date(y, m, 1), date(y, m, last_day)

        if rec.period_type == "quarter":
            q = int(rec.quarter or 1)
            q = 1 if q < 1 else (4 if q > 4 else q)
            start_m = (q - 1) * 3 + 1
            end_m = start_m + 2
            last_day = calendar.monthrange(y, end_m)[1]
            return date(y, start_m, 1), date(y, end_m, last_day)

        # year
        return date(y, 1, 1), date(y, 12, 31)

    def _dt_range(self, start_d, end_d):
        start_dt = datetime.combine(start_d, time.min)
        end_dt = datetime.combine(end_d, time.max).replace(microsecond=0)
        return start_dt, end_dt

    def _get_location_ids(self, rec):
        Location = self.env["stock.location"]
        company_id = rec.company_id.id if rec.company_id else self.env.company.id

        if rec.location_id:
            return Location.search([("id", "child_of", rec.location_id.id)]).ids

        return Location.search([
            ("usage", "=", "internal"),
            "|", ("company_id", "=", False), ("company_id", "=", company_id),
        ]).ids

    def _ml_qty_field(self):
        """Auto-detect qty field on stock.move.line."""
        SML = self.env["stock.move.line"].sudo()
        for f in ("qty_done", "quantity_done", "quantity", "product_uom_qty"):
            if f in SML._fields:
                return f
        raise ValueError(
            "Không tìm thấy field số lượng trên stock.move.line "
            "(qty_done/quantity_done/quantity/product_uom_qty)."
        )

    def _ml_date_field(self):
        """Prefer done date for accurate period filter."""
        SML = self.env["stock.move.line"].sudo()

        if "date" in SML._fields:
            return "date"

        Move = self.env["stock.move"].sudo()
        Picking = self.env["stock.picking"].sudo()
        if "picking_id" in Move._fields and "date_done" in Picking._fields:
            return "move_id.picking_id.date_done"

        return "move_id.date"

    def _rg_qty_by_move(self, domain):
        """Return dict {move_id: qty_sum} on stock.move.line (for prorate move.value_amount)."""
        SML = self.env["stock.move.line"].sudo()
        qty_field = self._ml_qty_field()
        res = SML.read_group(domain, [qty_field], ["move_id"])
        out = {}
        for r in res:
            mid = r.get("move_id") and r["move_id"][0]
            if mid:
                out[mid] = float(r.get(qty_field, 0.0) or 0.0)
        return out

    def _line_value(self, ml, qty, move_qty_map):
        """
        Compute value for a move line.
        Priority:
        1) stock.move.line.value_amount
        2) stock.move.line.unit_cost * qty
        3) stock.move.value_amount prorate by qty / sum(move qty)
        4) stock.move.unit_cost * qty
        5) product.standard_price * qty
        """
        Move = self.env["stock.move"].sudo()
        SML = self.env["stock.move.line"].sudo()

        has_ml_value_amount = "value_amount" in SML._fields
        has_ml_unit_cost = "unit_cost" in SML._fields
        has_mv_value_amount = "value_amount" in Move._fields
        has_mv_unit_cost = "unit_cost" in Move._fields

        qty = float(qty or 0.0)

        # 1) move line value_amount
        if has_ml_value_amount:
            va = float(getattr(ml, "value_amount", 0.0) or 0.0)
            if va:
                return va

        # 2) move line unit_cost
        if has_ml_unit_cost:
            uc = float(getattr(ml, "unit_cost", 0.0) or 0.0)
            if uc:
                return uc * qty

        m = ml.move_id

        # 3) move value_amount prorate
        if has_mv_value_amount:
            mv = float(getattr(m, "value_amount", 0.0) or 0.0)
            if mv:
                total_qty = float(move_qty_map.get(m.id, 0.0) or 0.0)
                if total_qty:
                    return mv * (qty / total_qty)
                return mv

        # 4) move unit_cost
        if has_mv_unit_cost:
            uc = float(getattr(m, "unit_cost", 0.0) or 0.0)
            if uc:
                return uc * qty

        # 5) fallback standard_price
        return float((ml.product_id.standard_price or 0.0)) * qty

    # -----------------
    # RPC
    # -----------------

    @api.model
    def inventory_report(self, option):
        wizard_id = option[0] if isinstance(option, (list, tuple)) and option else option
        rec = self.browse(wizard_id).exists()
        if not rec:
            return {"name": "Inventory Movement Summary", "orders": {}, "filters": {}, "report_lines": [], "totals": {}}

        start_d, end_d = self._compute_date_range(rec)
        start_dt, end_dt = self._dt_range(start_d, end_d)

        loc_ids = self._get_location_ids(rec)
        if not loc_ids:
            return {
                "name": "Inventory Movement Summary",
                "type": "ir.actions.client",
                "tag": "inv_r",
                "orders": {},
                "filters": {},
                "report_lines": [],
                "totals": {},
            }

        company_id = rec.company_id.id if rec.company_id else self.env.company.id
        date_field = self._ml_date_field()

        SML = self.env["stock.move.line"].sudo()
        qty_field = self._ml_qty_field()

        base = [
            ("move_id.state", "=", "done"),
            ("product_id.detailed_type", "=", "product"),
            ("move_id.company_id", "=", company_id),
        ]

        # ✅ nếu sau này bạn muốn loại internal transfer giữa loc_ids thì bật True
        exclude_internal_transfers = False

        start_dt_s = fields.Datetime.to_string(start_dt)
        end_dt_s = fields.Datetime.to_string(end_dt)

        # domain chung: mọi line có liên quan loc
        loc_domain = ["|", ("location_id", "in", loc_ids), ("location_dest_id", "in", loc_ids)]

        before_domain = base + loc_domain + [(date_field, "<", start_dt_s)]
        period_domain = base + loc_domain + [(date_field, ">=", start_dt_s), (date_field, "<=", end_dt_s)]

        ml_before = SML.search(before_domain)
        ml_period = SML.search(period_domain)

        move_qty_before = self._rg_qty_by_move(before_domain)
        move_qty_period = self._rg_qty_by_move(period_domain)

        agg = defaultdict(lambda: {
            "opening_in_qty": 0.0, "opening_in_val": 0.0,
            "opening_out_qty": 0.0, "opening_out_val": 0.0,
            "in_qty": 0.0, "in_val": 0.0,
            "out_qty": 0.0, "out_val": 0.0,
        })

        def _accumulate(mls, is_before: bool):
            move_qty_map = move_qty_before if is_before else move_qty_period
            for ml in mls:
                pid = ml.product_id.id
                if not pid:
                    continue

                qty = float(getattr(ml, qty_field, 0.0) or 0.0)
                if not qty:
                    continue

                in_flag = ml.location_dest_id.id in loc_ids
                out_flag = ml.location_id.id in loc_ids

                if exclude_internal_transfers and in_flag and out_flag:
                    continue

                val = float(self._line_value(ml, qty, move_qty_map) or 0.0)

                if is_before:
                    if in_flag:
                        agg[pid]["opening_in_qty"] += qty
                        agg[pid]["opening_in_val"] += val
                    if out_flag:
                        agg[pid]["opening_out_qty"] += qty
                        agg[pid]["opening_out_val"] += val
                else:
                    if in_flag:
                        agg[pid]["in_qty"] += qty
                        agg[pid]["in_val"] += val
                    if out_flag:
                        agg[pid]["out_qty"] += qty
                        agg[pid]["out_val"] += val

        _accumulate(ml_before, True)
        _accumulate(ml_period, False)

        product_ids = sorted(agg.keys())
        products = self.env["product.product"].sudo().browse(product_ids).exists()
        pmap = {p.id: p for p in products}

        lines = []
        totals = defaultdict(float)

        for pid in product_ids:
            p = pmap.get(pid)
            if not p:
                continue

            a = agg[pid]

            opening_qty = a["opening_in_qty"] - a["opening_out_qty"]
            opening_val = a["opening_in_val"] - a["opening_out_val"]

            in_qty = a["in_qty"]
            in_val = a["in_val"]

            out_qty = a["out_qty"]
            out_val = a["out_val"]

            closing_qty = opening_qty + in_qty - out_qty
            closing_val = opening_val + in_val - out_val

            if not opening_qty and not in_qty and not out_qty and not closing_qty:
                continue

            lines.append({
                "product_id": p.id,
                "product_name": p.name,
                "product_code": p.default_code or "",
                "uom": p.uom_id.name,

                "opening_qty": opening_qty,
                "opening_val": opening_val,

                "in_qty": in_qty,
                "in_val": in_val,

                "out_qty": out_qty,
                "out_val": out_val,

                "closing_qty": closing_qty,
                "closing_val": closing_val,
            })

            totals["opening_qty"] += opening_qty
            totals["opening_val"] += opening_val
            totals["in_qty"] += in_qty
            totals["in_val"] += in_val
            totals["out_qty"] += out_qty
            totals["out_val"] += out_val
            totals["closing_qty"] += closing_qty
            totals["closing_val"] += closing_val

        lines.sort(key=lambda x: (x.get("product_name") or ""))

        period_label = {
            "custom": "Custom",
            "month": "Month",
            "quarter": "Quarter",
            "year": "Year"
        }.get(rec.period_type, "Custom")

        filters = {
            "period_type": period_label,
            "date_from": fields.Date.to_string(start_d),
            "date_to": fields.Date.to_string(end_d),
            "location": rec.location_id.complete_name if rec.location_id else "All internal locations",
        }

        orders = {
            "period_type": rec.period_type,
            "date_from": fields.Date.to_string(rec.date_from) if rec.date_from else False,
            "date_to": fields.Date.to_string(rec.date_to) if rec.date_to else False,
            "month": rec.month,
            "quarter": rec.quarter,
            "year": rec.year,
            "location_id": rec.location_id.id if rec.location_id else False,
            "computed_date_from": fields.Date.to_string(start_d),
            "computed_date_to": fields.Date.to_string(end_d),
            "company_id": company_id,
        }

        return {
            "name": "Inventory Movement Summary",
            "type": "ir.actions.client",
            "tag": "inv_r",
            "orders": orders,
            "filters": filters,
            "report_lines": lines,
            "totals": totals,
        }

    # -----------------
    # XLSX
    # -----------------

    def get_inventory_xlsx_report(self, data, response, report_data, dfr_data):
        orders = json.loads(data or "{}")
        report_lines = json.loads(report_data or "[]")
        totals = {}
        try:
            dfr = json.loads(dfr_data or "{}")
            totals = dfr.get("totals") or {}
        except Exception:
            totals = {}

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {
            "in_memory": True,
        })
        sheet = workbook.add_worksheet("Inventory")

        # ===== FORMATS =====
        fmt_company = workbook.add_format({"bold": True, "font_size": 12})
        fmt_info = workbook.add_format({"bold": True})
        head = workbook.add_format({"align": "center", "bold": True, "font_size": 16})

        th2 = workbook.add_format({"align": "center", "valign": "vcenter", "bold": True, "border": 1})
        td2 = workbook.add_format({"border": 1})

        # ✅ tách format số: SL (2 lẻ) vs Giá trị (0 lẻ)
        num_qty = workbook.add_format({"border": 1, "align": "right", "num_format": "#,##0"})
        num_val = workbook.add_format({"border": 1, "align": "right", "num_format": "#,##0"})
        # nếu muốn âm đỏ: add {"font_color": "red"} cho số âm (tuỳ)

        # ===== COMPANY HEADER (3 dòng) =====
        cid = int(orders.get("company_id") or self.env.company.id)
        company = self.env["res.company"].browse(cid).exists()
        partner = company.partner_id if company else self.env.company.partner_id

        company_name = (company.name or "").upper() if company else (self.env.company.name or "").upper()
        raw_addr = partner._display_address(without_company=True) if partner else ""
        addr = ", ".join([p.strip() for p in raw_addr.replace("\n", ",").split(",") if p.strip()])
        vat = (company.vat if company else self.env.company.vat) or ""

        sheet.merge_range("A1:B1", company_name, fmt_company)
        if addr:
            sheet.merge_range("A2:B2", addr, fmt_info)
        if vat:
            sheet.merge_range("A3:B3", f"Mã số thuế: {vat}", fmt_info)

        # ===== TITLE =====
        sheet.merge_range("A4:K4", "BÁO CÁO TỒN KHO", head)

        # ===== SUB TITLE: Kho + kỳ =====
        loc_name = "All internal locations"
        loc_id = orders.get("location_id")
        if loc_id:
            loc = self.env["stock.location"].browse(int(loc_id)).exists()
            if loc:
                loc_name = loc.complete_name

        period_type = (orders.get("period_type") or "custom").strip()
        dfrom = orders.get("computed_date_from") or orders.get("date_from")
        dto = orders.get("computed_date_to") or orders.get("date_to")

        def _parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        d1 = _parse_date(dfrom) if dfrom else None
        d2 = _parse_date(dto) if dto else None

        sub_text = f"Kho: {loc_name}"
        if d1:
            y = d1.year
            m = d1.month
            q = ((m - 1) // 3) + 1

            if period_type == "month":
                sub_text = f"Kho: {loc_name}, Tháng {m} năm {y}"
            elif period_type == "quarter":
                sub_text = f"Kho: {loc_name}, Quý {q} năm {y}"
            elif period_type == "year":
                sub_text = f"Kho: {loc_name}, Năm {y}"
            else:
                if d2:
                    sub_text = f"Kho: {loc_name}, Từ ngày {d1.strftime('%d/%m/%Y')} đến ngày {d2.strftime('%d/%m/%Y')}"
                else:
                    sub_text = f"Kho: {loc_name}, Ngày {d1.strftime('%d/%m/%Y')}"

        fmt_sub = workbook.add_format({"align": "center", "italic": True, "bold": True})
        sheet.merge_range("A5:K5", sub_text, fmt_sub)

        # ===== TABLE HEADER (2 dòng cha + con) =====
        row_parent = 7
        row_child = 8

        sheet.merge_range(row_parent, 0, row_child, 0, "Mã hàng", th2)
        sheet.merge_range(row_parent, 1, row_child, 1, "Sản phẩm/Hàng hóa", th2)
        sheet.merge_range(row_parent, 2, row_child, 2, "Đơn vị", th2)

        sheet.merge_range(row_parent, 3, row_parent, 4, "Đầu kỳ", th2)
        sheet.merge_range(row_parent, 5, row_parent, 6, "Nhập", th2)
        sheet.merge_range(row_parent, 7, row_parent, 8, "Xuất", th2)
        sheet.merge_range(row_parent, 9, row_parent, 10, "Cuối kỳ", th2)

        sheet.write(row_child, 3, "SL", th2)
        sheet.write(row_child, 4, "Giá trị", th2)
        sheet.write(row_child, 5, "SL", th2)
        sheet.write(row_child, 6, "Giá trị", th2)
        sheet.write(row_child, 7, "SL", th2)
        sheet.write(row_child, 8, "Giá trị", th2)
        sheet.write(row_child, 9, "SL", th2)
        sheet.write(row_child, 10, "Giá trị", th2)

        sheet.set_column(0, 0, 18)
        sheet.set_column(1, 1, 45)
        sheet.set_column(2, 2, 12)
        sheet.set_column(3, 10, 16)

        # ===== TOTAL ROW =====
        row = row_child + 1
        sheet.merge_range(row, 0, row, 2, "Tổng", th2)

        sheet.write_number(row, 3, float(totals.get("opening_qty") or 0.0), num_qty)
        sheet.write_number(row, 4, float(totals.get("opening_val") or 0.0), num_val)
        sheet.write_number(row, 5, float(totals.get("in_qty") or 0.0), num_qty)
        sheet.write_number(row, 6, float(totals.get("in_val") or 0.0), num_val)
        sheet.write_number(row, 7, float(totals.get("out_qty") or 0.0), num_qty)
        sheet.write_number(row, 8, float(totals.get("out_val") or 0.0), num_val)
        sheet.write_number(row, 9, float(totals.get("closing_qty") or 0.0), num_qty)
        sheet.write_number(row, 10, float(totals.get("closing_val") or 0.0), num_val)

        # ===== DATA ROWS =====
        for line in report_lines:
            row += 1

            code = line.get("product_code") or ""
            if not code and line.get("product_id"):
                p = self.env["product.product"].sudo().browse(int(line["product_id"])).exists()
                code = (p.default_code or "") if p else ""

            sheet.write(row, 0, code, td2)
            sheet.write(row, 1, line.get("product_name", ""), td2)
            sheet.write(row, 2, line.get("uom", ""), td2)

            sheet.write_number(row, 3, float(line.get("opening_qty") or 0.0), num_qty)
            sheet.write_number(row, 4, float(line.get("opening_val") or 0.0), num_val)
            sheet.write_number(row, 5, float(line.get("in_qty") or 0.0), num_qty)
            sheet.write_number(row, 6, float(line.get("in_val") or 0.0), num_val)
            sheet.write_number(row, 7, float(line.get("out_qty") or 0.0), num_qty)
            sheet.write_number(row, 8, float(line.get("out_val") or 0.0), num_val)
            sheet.write_number(row, 9, float(line.get("closing_qty") or 0.0), num_qty)
            sheet.write_number(row, 10, float(line.get("closing_val") or 0.0), num_val)
        workbook.close()
        output.seek(0)
        response.stream.write(output.read())
        output.close()