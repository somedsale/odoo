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
    month = fields.Selection([(str(i), str(i)) for i in range(1, 13)], string="Month")
    quarter = fields.Selection([("1", "Q1"), ("2", "Q2"), ("3", "Q3"), ("4", "Q4")], string="Quarter")
    year = fields.Integer(string="Year", default=lambda self: fields.Date.context_today(self).year)

    location_id = fields.Many2one("stock.location", string="Location")
    company_id = fields.Many2one("res.company", string="Company", default=lambda self: self.env.company)

    # =================
    # Helpers
    # =================

    def _compute_date_range(self, rec):
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
        SML = self.env["stock.move.line"].sudo()
        for f in ("qty_done", "quantity_done", "quantity", "product_uom_qty"):
            if f in SML._fields:
                return f
        raise ValueError(
            "Không tìm thấy field số lượng trên stock.move.line "
            "(qty_done/quantity_done/quantity/product_uom_qty)."
        )

    def _ml_date_field(self):
        SML = self.env["stock.move.line"].sudo()

        if "date" in SML._fields:
            return "date"

        Move = self.env["stock.move"].sudo()
        Picking = self.env["stock.picking"].sudo()
        if "picking_id" in Move._fields and "date_done" in Picking._fields:
            return "move_id.picking_id.date_done"

        return "move_id.date"

    def _rg_qty_by_move(self, domain):
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
        Move = self.env["stock.move"].sudo()
        SML = self.env["stock.move.line"].sudo()

        has_ml_value_amount = "value_amount" in SML._fields
        has_ml_unit_cost = "unit_cost" in SML._fields
        has_mv_value_amount = "value_amount" in Move._fields
        has_mv_unit_cost = "unit_cost" in Move._fields

        qty = float(qty or 0.0)

        if has_ml_value_amount:
            va = float(getattr(ml, "value_amount", 0.0) or 0.0)
            if va:
                return va

        if has_ml_unit_cost:
            uc = float(getattr(ml, "unit_cost", 0.0) or 0.0)
            if uc:
                return uc * qty

        m = ml.move_id

        if has_mv_value_amount:
            mv = float(getattr(m, "value_amount", 0.0) or 0.0)
            if mv:
                total_qty = float(move_qty_map.get(m.id, 0.0) or 0.0)
                if total_qty:
                    return mv * (qty / total_qty)
                return mv

        if has_mv_unit_cost:
            uc = float(getattr(m, "unit_cost", 0.0) or 0.0)
            if uc:
                return uc * qty

        return float((ml.product_id.standard_price or 0.0)) * qty

    def _get_base_domains(self, rec):
        start_d, end_d = self._compute_date_range(rec)
        start_dt, end_dt = self._dt_range(start_d, end_d)
        company_id = rec.company_id.id if rec.company_id else self.env.company.id
        loc_ids = self._get_location_ids(rec)
        date_field = self._ml_date_field()

        base = [
            ("move_id.state", "=", "done"),
            ("product_id.detailed_type", "=", "product"),
            ("move_id.company_id", "=", company_id),
        ]
        loc_domain = ["|", ("location_id", "in", loc_ids), ("location_dest_id", "in", loc_ids)]

        start_dt_s = fields.Datetime.to_string(start_dt)
        end_dt_s = fields.Datetime.to_string(end_dt)

        before_domain = base + loc_domain + [(date_field, "<", start_dt_s)]
        period_domain = base + loc_domain + [(date_field, ">=", start_dt_s), (date_field, "<=", end_dt_s)]

        return {
            "start_d": start_d,
            "end_d": end_d,
            "start_dt": start_dt,
            "end_dt": end_dt,
            "company_id": company_id,
            "loc_ids": loc_ids,
            "date_field": date_field,
            "before_domain": before_domain,
            "period_domain": period_domain,
        }

    def _movement_type_label(self, ml, loc_ids):
        in_flag = ml.location_dest_id.id in loc_ids
        out_flag = ml.location_id.id in loc_ids

        if in_flag and out_flag:
            return "Nội bộ"
        if in_flag:
            return "Nhập"
        if out_flag:
            return "Xuất"
        return "Khác"

    # =================
    # RPC SUMMARY
    # =================

    @api.model
    def inventory_report(self, option):
        wizard_id = option[0] if isinstance(option, (list, tuple)) and option else option
        rec = self.browse(wizard_id).exists()
        if not rec:
            return {"name": "Inventory Movement Summary", "orders": {}, "filters": {}, "report_lines": [], "totals": {}}

        ctx = self._get_base_domains(rec)
        loc_ids = ctx["loc_ids"]

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

        SML = self.env["stock.move.line"].sudo()
        qty_field = self._ml_qty_field()

        ml_before = SML.search(ctx["before_domain"])
        ml_period = SML.search(ctx["period_domain"])

        move_qty_before = self._rg_qty_by_move(ctx["before_domain"])
        move_qty_period = self._rg_qty_by_move(ctx["period_domain"])

        agg = defaultdict(lambda: {
            "opening_in_qty": 0.0, "opening_in_val": 0.0,
            "opening_out_qty": 0.0, "opening_out_val": 0.0,
            "in_qty": 0.0, "in_val": 0.0,
            "out_qty": 0.0, "out_val": 0.0,
        })

        exclude_internal_transfers = False

        def _accumulate(mls, is_before=False):
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
                "product_name": p.display_name or p.name,
                "product_code": p.default_code or "",
                "uom": p.uom_id.name or "",

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

        lines.sort(key=lambda x: ((x.get("product_name") or "").lower(), (x.get("product_code") or "").lower()))

        period_label = {
            "custom": "Custom",
            "month": "Month",
            "quarter": "Quarter",
            "year": "Year",
        }.get(rec.period_type, "Custom")

        filters = {
            "period_type": period_label,
            "date_from": fields.Date.to_string(ctx["start_d"]),
            "date_to": fields.Date.to_string(ctx["end_d"]),
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
            "computed_date_from": fields.Date.to_string(ctx["start_d"]),
            "computed_date_to": fields.Date.to_string(ctx["end_d"]),
            "company_id": ctx["company_id"],
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

    # =================
    # RPC DETAIL
    # =================

    @api.model
    def inventory_product_detail(self, wizard_id, product_id):
        rec = self.browse(wizard_id).exists()
        if not rec or not product_id:
            return {
                "product": {},
                "lines": [],
                "summary": {},
            }

        ctx = self._get_base_domains(rec)
        loc_ids = ctx["loc_ids"]
        qty_field = self._ml_qty_field()
        SML = self.env["stock.move.line"].sudo()

        domain = list(ctx["period_domain"]) + [("product_id", "=", int(product_id))]
        mls = SML.search(domain)

        move_qty_map = self._rg_qty_by_move(domain)
        product = self.env["product.product"].sudo().browse(int(product_id)).exists()

        detail_lines = []
        sum_in_qty = 0.0
        sum_in_val = 0.0
        sum_out_qty = 0.0
        sum_out_val = 0.0

        for ml in mls:
            qty = float(getattr(ml, qty_field, 0.0) or 0.0)
            if not qty:
                continue

            movement_type = self._movement_type_label(ml, loc_ids)
            val = float(self._line_value(ml, qty, move_qty_map) or 0.0)

            if movement_type == "Nhập":
                sum_in_qty += qty
                sum_in_val += val
            elif movement_type == "Xuất":
                sum_out_qty += qty
                sum_out_val += val

            movement_date = (
                getattr(ml, "date", False)
                or getattr(ml.move_id, "date", False)
                or getattr(getattr(ml.move_id, "picking_id", False), "date_done", False)
            )

            detail_lines.append({
                "id": ml.id,
                "sort_date": fields.Datetime.to_string(movement_date) if movement_date else "",
                "date": fields.Datetime.to_string(movement_date) if movement_date else "",
                "reference": (
                    getattr(getattr(ml, "move_id", False), "reference", False)
                    or getattr(getattr(ml, "move_id", False), "origin", False)
                    or getattr(getattr(getattr(ml, "move_id", False), "picking_id", False), "name", False)
                    or getattr(getattr(ml, "move_id", False), "name", False)
                    or ""
                ),
                "picking_name": getattr(getattr(ml.move_id, "picking_id", False), "name", False) or "",
                "location_from": ml.location_id.complete_name or "",
                "location_to": ml.location_dest_id.complete_name or "",
                "movement_type": movement_type,
                "qty": qty,
                "value": val,
                "uom": ml.product_uom_id.name or (product.uom_id.name if product else ""),
                "partner": (
                    getattr(getattr(ml.move_id, "picking_id", False), "partner_id", False)
                    and ml.move_id.picking_id.partner_id.display_name
                ) or "",
                "lot_name": ("lot_id" in ml._fields and ml.lot_id and ml.lot_id.name) or "",
            })

        detail_lines = sorted(
            detail_lines,
            key=lambda x: (x.get("sort_date") or "", x.get("id") or 0)
        )

        for line in detail_lines:
            line.pop("sort_date", None)

        return {
            "product": {
                "id": product.id if product else False,
                "name": product.display_name if product else "",
                "code": product.default_code if product else "",
                "uom": product.uom_id.name if product else "",
            },
            "summary": {
                "in_qty": sum_in_qty,
                "in_val": sum_in_val,
                "out_qty": sum_out_qty,
                "out_val": sum_out_val,
            },
            "lines": detail_lines,
        }
        rec = self.browse(wizard_id).exists()
        if not rec or not product_id:
            return {
                "product": {},
                "lines": [],
                "summary": {},
            }

        ctx = self._get_base_domains(rec)
        loc_ids = ctx["loc_ids"]
        qty_field = self._ml_qty_field()
        SML = self.env["stock.move.line"].sudo()

        domain = list(ctx["period_domain"]) + [("product_id", "=", int(product_id))]
        mls = SML.search(domain, order="%s asc, id asc" % ctx["date_field"])

        move_qty_map = self._rg_qty_by_move(domain)
        product = self.env["product.product"].sudo().browse(int(product_id)).exists()

        detail_lines = []
        sum_in_qty = 0.0
        sum_in_val = 0.0
        sum_out_qty = 0.0
        sum_out_val = 0.0

        for ml in mls:
            qty = float(getattr(ml, qty_field, 0.0) or 0.0)
            if not qty:
                continue

            movement_type = self._movement_type_label(ml, loc_ids)
            val = float(self._line_value(ml, qty, move_qty_map) or 0.0)

            if movement_type == "Nhập":
                sum_in_qty += qty
                sum_in_val += val
            elif movement_type == "Xuất":
                sum_out_qty += qty
                sum_out_val += val

            detail_lines.append({
                "id": ml.id,
                "date": fields.Datetime.to_string(
                    getattr(ml, "date", False)
                    or getattr(ml.move_id, "date", False)
                    or getattr(getattr(ml.move_id, "picking_id", False), "date_done", False)
                ) if (
                    getattr(ml, "date", False)
                    or getattr(ml.move_id, "date", False)
                    or getattr(getattr(ml.move_id, "picking_id", False), "date_done", False)
                ) else "",
                "reference": (
                    getattr(getattr(ml, "move_id", False), "reference", False)
                    or getattr(getattr(ml, "move_id", False), "origin", False)
                    or getattr(getattr(getattr(ml, "move_id", False), "picking_id", False), "name", False)
                    or getattr(getattr(ml, "move_id", False), "name", False)
                    or ""
                ),
                "picking_name": getattr(getattr(ml.move_id, "picking_id", False), "name", False) or "",
                "location_from": ml.location_id.complete_name or "",
                "location_to": ml.location_dest_id.complete_name or "",
                "movement_type": movement_type,
                "qty": qty,
                "value": val,
                "uom": ml.product_uom_id.name or product.uom_id.name or "",
                "partner": (
                    getattr(getattr(ml.move_id, "picking_id", False), "partner_id", False)
                    and ml.move_id.picking_id.partner_id.display_name
                ) or "",
                "lot_name": (
                    "lot_id" in ml._fields and ml.lot_id and ml.lot_id.name
                ) or "",
            })

        return {
            "product": {
                "id": product.id if product else False,
                "name": product.display_name if product else "",
                "code": product.default_code if product else "",
                "uom": product.uom_id.name if product else "",
            },
            "summary": {
                "in_qty": sum_in_qty,
                "in_val": sum_in_val,
                "out_qty": sum_out_qty,
                "out_val": sum_out_val,
            },
            "lines": detail_lines,
        }

    # =================
    # XLSX
    # =================

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
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        sheet = workbook.add_worksheet("Inventory")

        fmt_company = workbook.add_format({"bold": True, "font_size": 12})
        fmt_info = workbook.add_format({"bold": True})
        head = workbook.add_format({"align": "center", "bold": True, "font_size": 16})
        fmt_sub = workbook.add_format({"align": "center", "italic": True})

        th2 = workbook.add_format({"align": "center", "valign": "vcenter", "bold": True, "border": 1})
        td2 = workbook.add_format({"border": 1})
        num_qty = workbook.add_format({"border": 1, "align": "right", "num_format": "#,##0.00"})
        num_val = workbook.add_format({"border": 1, "align": "right", "num_format": "#,##0.00"})

        cid = int(orders.get("company_id") or self.env.company.id)
        company = self.env["res.company"].browse(cid).exists()
        partner = company.partner_id if company else self.env.company.partner_id

        company_name = (company.name or self.env.company.name or "").upper()
        raw_addr = partner._display_address(without_company=True) if partner else ""
        addr = ", ".join([p.strip() for p in raw_addr.replace("\n", ",").split(",") if p.strip()])
        vat = (company.vat if company else self.env.company.vat) or ""

        sheet.merge_range("A1:B1", company_name, fmt_company)
        if addr:
            sheet.merge_range("A2:B2", addr, fmt_info)
        if vat:
            sheet.merge_range("A3:B3", "Mã số thuế: %s" % vat, fmt_info)

        sheet.merge_range("A4:K4", "BÁO CÁO TỒN KHO", head)

        loc_name = "All internal locations"
        loc_id = orders.get("location_id")
        if loc_id:
            loc = self.env["stock.location"].browse(int(loc_id)).exists()
            if loc:
                loc_name = loc.complete_name

        date_from = orders.get("computed_date_from") or ""
        date_to = orders.get("computed_date_to") or ""
        sub_text = "Kho: %s | Từ ngày: %s | Đến ngày: %s" % (loc_name, date_from, date_to)
        sheet.merge_range("A5:K5", sub_text, fmt_sub)

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

        for line in report_lines:
            row += 1
            sheet.write(row, 0, line.get("product_code") or "", td2)
            sheet.write(row, 1, line.get("product_name") or "", td2)
            sheet.write(row, 2, line.get("uom") or "", td2)

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