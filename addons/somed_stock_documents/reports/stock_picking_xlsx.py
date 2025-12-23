# -*- coding: utf-8 -*-
import base64
import io

from odoo import models


class StockPickingXlsxMixin(object):
    """
    Mixin Python thuần (KHÔNG kế thừa models.AbstractModel) để tránh MRO conflict.
    Xuất Excel theo layout PDF custom:
    - Header: Logo + thông tin công ty
    - Tiêu đề + ngày + số
    - Info
    - Bảng chi tiết + tổng
    - Số tiền bằng chữ (Dong -> Đồng)
    - Chứng từ gốc kèm theo
    - Chữ ký 4 cột
    """

    # -------------------------
    # Helpers
    # -------------------------
    def _safe_str(self, v):
        return "" if v is None else str(v)

    def _safe_len(self, v):
        if v is None:
            return 0
        return len(str(v))

    def _strip_prefix_wh(self, name):
        """
        WH/PNK/00007 -> PNK/00007
        WH1/PNK/00007 -> PNK/00007
        """
        if not name:
            return ""
        s = str(name)
        if s.startswith("WH/"):
            return s[3:]
        parts = s.split("/")
        if len(parts) >= 3 and parts[0].upper().startswith("WH"):
            return "/".join(parts[1:])
        return s

    def _amount_to_text_vn(self, currency, amount):
        txt = (currency and currency.amount_to_text(amount)) or ""
        return (
            txt.replace("Dong", "Đồng")
               .replace("DONG", "ĐỒNG")
               .replace("dong", "đồng")
        )

    def _autofit_columns(self, ws, col_maxlen, fixed_width=None):
        fixed_width = fixed_width or {}
        MIN_W = 6
        MAX_W = 55
        col_widths = {}

        for col, maxlen in col_maxlen.items():
            if col in fixed_width:
                w = fixed_width[col]
                ws.set_column(col, col, w)
                col_widths[col] = w
                continue

            w = int(max(MIN_W, min(MAX_W, maxlen * 1.05 + 2)))
            ws.set_column(col, col, w)
            col_widths[col] = w
        return col_widths

    def _autofit_row_height(self, ws, row_idx, values, col_widths, base=18, max_h=90):
        max_lines = 1
        for c, v in enumerate(values):
            if v is None:
                continue
            s = str(v)
            if not s:
                continue
            for line in s.split("\n"):
                w = col_widths.get(c, 12)
                est = max(1, int((len(line) / max(w, 1)) + 0.999))
                max_lines = max(max_lines, est)

        h = min(max_h, base * max_lines)
        ws.set_row(row_idx, h)

    # -------------------------
    # Formats
    # -------------------------
    def _init_formats(self, workbook):
        fmt_title = workbook.add_format({
            "bold": True, "font_size": 16, "align": "center", "valign": "vcenter"
        })
        fmt_subtitle = workbook.add_format({
            "italic": True, "bold": True, "font_size": 11, "align": "center", "valign": "vcenter"
        })
        fmt_center = workbook.add_format({"align": "center", "valign": "vcenter"})
        fmt_left = workbook.add_format({"align": "left", "valign": "vcenter"})
        fmt_left_wrap = workbook.add_format({"align": "left", "valign": "top", "text_wrap": True})
        fmt_right = workbook.add_format({"align": "right", "valign": "vcenter"})
        fmt_small_right = workbook.add_format({"align": "right", "valign": "vcenter", "font_size": 9})
        fmt_small_right_caps = workbook.add_format({"align": "right", "valign": "vcenter", "font_size": 9, "bold": True})
        fmt_th = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})

        fmt_td = workbook.add_format({"border": 1, "valign": "vcenter"})
        fmt_td_center = workbook.add_format({"border": 1, "align": "center", "valign": "vcenter"})
        fmt_td_left_wrap = workbook.add_format({"border": 1, "align": "left", "valign": "top", "text_wrap": True})

        fmt_money = workbook.add_format({"border": 1, "align": "right", "valign": "vcenter", "num_format": "#,##0"})
        fmt_money_bold = workbook.add_format({"border": 1, "bold": True, "align": "right", "valign": "vcenter", "num_format": "#,##0"})
        fmt_qty = workbook.add_format({"border": 1, "align": "right", "valign": "vcenter", "num_format": "#,##0.##"})
        fmt_total_label = workbook.add_format({"border": 1, "bold": True, "align": "right", "valign": "vcenter"})
        fmt_bold = workbook.add_format({"bold": True})
        fmt_italic = workbook.add_format({"italic": True})
        fmt_bold_italic = workbook.add_format({"bold": True, "italic": True})

        return {
            "title": fmt_title,
            "subtitle": fmt_subtitle,
            "center": fmt_center,
            "left": fmt_left,
            "left_wrap": fmt_left_wrap,
            "right": fmt_right,
            "small_right": fmt_small_right,
            "small_right_caps": fmt_small_right_caps,
            "th": fmt_th,
            "td": fmt_td,
            "td_center": fmt_td_center,
            "td_left_wrap": fmt_td_left_wrap,
            "money": fmt_money,
            "money_bold": fmt_money_bold,
            "qty": fmt_qty,
            "total_label": fmt_total_label,
            "bold": fmt_bold,
            "italic": fmt_italic,
            "bold_italic": fmt_bold_italic,
        }

    # -------------------------
    # Sheet print settings
    # -------------------------
    def _setup_sheet_print(self, ws):
        ws.set_paper(9)       # A4
        ws.set_landscape()
        ws.fit_to_pages(1, 0) # fit width 1 page
        ws.set_margins(0.3, 0.3, 0.4, 0.4)

    # -------------------------
    # Header giống external_layout (Logo + Info công ty)
    # -------------------------
    def _write_company_header(self, ws, company, fmts, row):
        """
        Layout tương tự:
        | Logo (trái) | Thông tin công ty (phải) |
        """
        # cho đẹp: hàng logo cao hơn
        ws.set_row(row, 55)

        # Logo bên trái (A..D)
        if company and company.logo:
            try:
                img_bytes = base64.b64decode(company.logo)
                image_stream = io.BytesIO(img_bytes)
                # đặt logo tại ô A1 (row, col=0)
                ws.insert_image(row, 0, "logo.png", {
                    "image_data": image_stream,
                    "x_scale": 0.35,
                    "y_scale": 0.35,
                    "x_offset": 2,
                    "y_offset": 2,
                })
            except Exception:
                pass

        # Info bên phải (E..J)
        partner = company.partner_id if company else False
        name = (company.name or "").upper() if company else ""
        vat = partner.vat if partner and partner.vat else ""
        street = partner.street if partner and partner.street else ""
        phone = getattr(company, "phone_accounting", "") if company else ""
        email = getattr(company, "account_email", "") if company else ""

        # viết dạng nhiều dòng giống PDF
        ws.merge_range(row, 4, row, 9, name, fmts["small_right_caps"])
        row += 1
        ws.merge_range(row, 4, row, 9, ("MST: %s" % vat) if vat else "", fmts["small_right"])
        row += 1
        ws.merge_range(row, 4, row, 9, ("Địa chỉ: %s" % street) if street else "", fmts["small_right"])
        row += 1
        ws.merge_range(row, 4, row, 9, ("SĐT: %s" % phone) if phone else "", fmts["small_right"])
        row += 1
        ws.merge_range(row, 4, row, 9, ("Email: %s" % email) if email else "", fmts["small_right"])

        return row + 1  # chừa 1 dòng cách

    # -------------------------
    # Blocks
    # -------------------------
    def _write_title_block(self, ws, o, title, fmts, row):
        ws.merge_range(row, 0, row, 9, title, fmts["title"])
        ws.set_row(row, 24)
        row += 1

        d = o.date_done
        dd = d.strftime("%d") if d else ""
        mm = d.strftime("%m") if d else ""
        yy = d.strftime("%Y") if d else ""
        ws.merge_range(row, 0, row, 9, f"Ngày {dd}  Tháng {mm}  Năm {yy}", fmts["subtitle"])
        ws.set_row(row, 18)
        row += 1

        so = self._strip_prefix_wh(o.name)
        ws.merge_range(row, 0, row, 9, f"Số: {so}", fmts["center"])
        ws.set_row(row, 16)
        row += 1
        return row

    def _write_info_block_pnk(self, ws, o, fmts, row):
        ws.write(row, 0, "Người giao hàng:", fmts["bold"])
        ws.merge_range(row, 1, row, 9, o.partner_id.display_name if o.partner_id else "", fmts["left"])
        row += 1

        ws.write(row, 0, "Nhập tại kho:", fmts["bold"])
        ws.merge_range(row, 1, row, 9, o.location_dest_id.complete_name if o.location_dest_id else "", fmts["left"])
        row += 1
        return row

    def _write_info_block_pxk(self, ws, o, fmts, row):
        ws.write(row, 0, "Người nhận hàng:", fmts["bold"])
        ws.merge_range(row, 1, row, 9, o.partner_id.display_name if o.partner_id else "", fmts["left"])
        row += 1

        ws.write(row, 0, "Lý do xuất kho:", fmts["bold"])
        ws.merge_range(row, 1, row, 9, self._safe_str(getattr(o, "delivery_reason", "")), fmts["left"])
        row += 1

        ws.write(row, 0, "Xuất tại kho:", fmts["bold"])
        ws.merge_range(row, 1, row, 9, o.location_id.complete_name if o.location_id else "", fmts["left"])
        row += 1
        return row

    def _write_table_header(self, ws, fmts, row):
        ws.merge_range(row, 0, row + 1, 0, "STT", fmts["th"])
        ws.merge_range(row, 1, row + 1, 1, "Sản phẩm", fmts["th"])
        ws.merge_range(row, 2, row + 1, 2, "Mã số", fmts["th"])
        ws.merge_range(row, 3, row + 1, 3, "ĐVT", fmts["th"])
        ws.merge_range(row, 4, row, 5, "Số lượng", fmts["th"])
        ws.write(row + 1, 4, "Nhu cầu", fmts["th"])
        ws.write(row + 1, 5, "Thực nhập", fmts["th"])
        ws.merge_range(row, 6, row + 1, 6, "Đơn giá", fmts["th"])
        ws.merge_range(row, 7, row + 1, 7, "Thành tiền", fmts["th"])
        ws.merge_range(row, 8, row + 1, 8, "Thuế", fmts["th"])
        ws.merge_range(row, 9, row + 1, 9, "Sau thuế", fmts["th"])
        ws.set_row(row, 20)
        ws.set_row(row + 1, 20)
        return row + 2

    def _write_table_lines(self, ws, o, fmts, row):
        currency = o.company_id.currency_id if o.company_id else o.env.company.currency_id

        line_no = 0
        sum_sub = 0.0
        sum_tax = 0.0
        sum_total = 0.0

        col_maxlen = {i: 0 for i in range(10)}
        written_rows = []

        lines = o.move_line_ids_without_package
        if not lines:
            ws.merge_range(row, 0, row, 9, "Không có dòng sản phẩm.", fmts["center"])
            ws.set_row(row, 18)
            return row + 1, sum_sub, sum_tax, sum_total, currency

        for ml in lines:
            line_no += 1

            product_name = ml.product_id.display_name if ml.product_id else ""
            code = ml.product_id.default_code if ml.product_id else ""
            uom = ml.product_uom_id.name if ml.product_uom_id else ""

            qty_done = ml.quantity or 0.0
            demand = (ml.move_id.product_uom_qty if ml.move_id else 0.0) or 0.0

            # THEO MODEL CUSTOM (stock.move.line)
            unit_sub = ml.unit_cost or 0.0
            line_sub = ml.price_subtotal if ml.price_subtotal is not None else (unit_sub * qty_done)
            line_tax = ml.price_tax or 0.0
            line_total = ml.price_total if ml.price_total is not None else (line_sub + line_tax)

            sum_sub += line_sub
            sum_tax += line_tax
            sum_total += line_total

            ws.write_number(row, 0, line_no, fmts["td_center"])
            ws.write(row, 1, product_name, fmts["td_left_wrap"])
            ws.write(row, 2, code or "", fmts["td"])
            ws.write(row, 3, uom or "", fmts["td_center"])
            ws.write_number(row, 4, demand, fmts["qty"])
            ws.write_number(row, 5, qty_done, fmts["qty"])
            ws.write_number(row, 6, unit_sub, fmts["money"])
            ws.write_number(row, 7, line_sub, fmts["money"])
            ws.write_number(row, 8, line_tax, fmts["money"])
            ws.write_number(row, 9, line_total, fmts["money"])

            col_maxlen[0] = max(col_maxlen[0], self._safe_len(line_no))
            col_maxlen[1] = max(col_maxlen[1], self._safe_len(product_name))
            col_maxlen[2] = max(col_maxlen[2], self._safe_len(code))
            col_maxlen[3] = max(col_maxlen[3], self._safe_len(uom))

            written_rows.append((row, [line_no, product_name, code, uom, demand, qty_done, unit_sub, line_sub, line_tax, line_total]))
            row += 1

        ws.merge_range(row, 0, row, 6, "TỔNG CỘNG", fmts["total_label"])
        ws.write_number(row, 7, sum_sub, fmts["money_bold"])
        ws.write_number(row, 8, sum_tax, fmts["money_bold"])
        ws.write_number(row, 9, sum_total, fmts["money_bold"])
        ws.set_row(row, 20)
        row += 1

        fixed = {
            0: 6, 2: 14, 3: 10, 4: 12, 5: 12, 6: 16, 7: 16, 8: 14, 9: 18
        }
        col_widths = self._autofit_columns(ws, col_maxlen, fixed_width=fixed)

        for r_idx, vals in written_rows:
            self._autofit_row_height(ws, r_idx, vals, col_widths, base=18, max_h=90)

        return row, sum_sub, sum_tax, sum_total, currency

    def _collect_related_docs(self, o):
        po_names = []
        inv_labels = []
        seen_po = set()
        seen_inv = set()

        for ml in o.move_line_ids_without_package:
            pol = ml.move_id.purchase_line_id if ml.move_id and getattr(ml.move_id, "purchase_line_id", False) else False
            po = pol.order_id if pol else False

            if po and po.name and po.name not in seen_po:
                seen_po.add(po.name)
                po_names.append(po.name)

            if po and getattr(po, "supplier_invoice_ids", False):
                for inv in po.supplier_invoice_ids:
                    label = inv.name or getattr(inv, "code", False) or getattr(inv, "number", False) or inv.ref or ""
                    if label and label not in seen_inv:
                        seen_inv.add(label)
                        inv_labels.append(label)

        mmo = False
        if o.origin:
            mmo = o.env["multi.mrp.order"].search([("name", "=", o.origin)], limit=1)

        contract = getattr(o, "contract_id", False)

        return {
            "po_names": ", ".join(po_names),
            "inv_names": ", ".join(inv_labels),
            "mmo_name": (mmo.name if mmo else ""),
            "contract_name": (contract.display_name if contract else ""),
        }

    def _write_amount_and_related(self, ws, o, fmts, row, currency, sum_total):
        ws.write(row, 0, "Số tiền bằng chữ:", fmts["bold"])
        amt_txt = self._amount_to_text_vn(currency, sum_total)
        ws.merge_range(row, 1, row, 9, amt_txt, fmts["bold_italic"])
        ws.set_row(row, 18)
        row += 1

        ws.write(row, 0, "Chứng từ gốc kèm theo:", fmts["bold"])
        row += 1

        docs = self._collect_related_docs(o)

        if docs["po_names"]:
            ws.write(row, 0, "- Đơn mua hàng:", fmts["left"])
            ws.merge_range(row, 1, row, 9, docs["po_names"], fmts["left_wrap"])
            row += 1

        if docs["inv_names"]:
            ws.write(row, 0, "- Hóa đơn NCC:", fmts["left"])
            ws.merge_range(row, 1, row, 9, docs["inv_names"], fmts["left_wrap"])
            row += 1

        if docs["mmo_name"]:
            ws.write(row, 0, "- Lệnh sản xuất:", fmts["left"])
            ws.merge_range(row, 1, row, 9, docs["mmo_name"], fmts["left_wrap"])
            row += 1

        if docs["contract_name"]:
            ws.write(row, 0, "- Hợp đồng:", fmts["left"])
            ws.merge_range(row, 1, row, 9, docs["contract_name"], fmts["left_wrap"])
            row += 1

        return row + 1

    def _write_signatures(self, ws, fmts, row):
        ws.merge_range(row, 0, row, 6, "", fmts["left"])
        ws.merge_range(row, 7, row, 9, "Ngày ... tháng ... năm ...", fmts["italic"])
        ws.set_row(row, 18)
        row += 1

        titles = [
            "Người lập biểu",
            "Người giao hàng",
            "Thủ Kho",
            "Kế toán trưởng\n(Hoặc bộ phận có nhu cầu)",
        ]
        note = "(Ký, ghi rõ họ tên)"

        ws.merge_range(row, 0, row, 1, titles[0], fmts["center"])
        ws.merge_range(row, 2, row, 4, titles[1], fmts["center"])
        ws.merge_range(row, 5, row, 7, titles[2], fmts["center"])
        ws.merge_range(row, 8, row, 9, titles[3], fmts["center"])
        ws.set_row(row, 28)
        row += 1

        ws.set_row(row, 60)
        row += 1

        ws.merge_range(row, 0, row, 1, note, fmts["center"])
        ws.merge_range(row, 2, row, 4, note, fmts["center"])
        ws.merge_range(row, 5, row, 7, note, fmts["center"])
        ws.merge_range(row, 8, row, 9, note, fmts["center"])
        ws.set_row(row, 18)
        row += 1

        return row

    # -------------------------
    # Render one picking
    # -------------------------
    def _render_picking(self, workbook, o, is_pnk=True):
        name = self._strip_prefix_wh(o.name) or (o.name or "")
        sheet_title = ((("PNK " if is_pnk else "PXK ") + name)[:31]) or ("PNK" if is_pnk else "PXK")
        ws = workbook.add_worksheet(sheet_title)

        self._setup_sheet_print(ws)
        fmts = self._init_formats(workbook)

        # base widths (autofit sẽ chỉnh lại)
        ws.set_column(0, 0, 6)
        ws.set_column(1, 1, 38)
        ws.set_column(2, 2, 14)
        ws.set_column(3, 3, 10)
        ws.set_column(4, 5, 12)
        ws.set_column(6, 9, 16)

        row = 0

        # ✅ Header giống template
        company = o.company_id or o.env.company
        row = self._write_company_header(ws, company, fmts, row)

        # Title
        row = self._write_title_block(ws, o, "PHIẾU NHẬP KHO" if is_pnk else "PHIẾU XUẤT KHO", fmts, row)

        # Info
        if is_pnk:
            row = self._write_info_block_pnk(ws, o, fmts, row)
        else:
            row = self._write_info_block_pxk(ws, o, fmts, row)

        row += 1

        # Table
        table_start = row
        row = self._write_table_header(ws, fmts, row)
        row, sum_sub, sum_tax, sum_total, currency = self._write_table_lines(ws, o, fmts, row)

        # Freeze header table
        ws.freeze_panes(table_start + 2, 0)

        row += 1
        row = self._write_amount_and_related(ws, o, fmts, row, currency, sum_total)
        row = self._write_signatures(ws, fmts, row)

    def _generate(self, workbook, data, docs, is_pnk=True):
        for o in docs:
            self._render_picking(workbook, o, is_pnk=is_pnk)


# =========================================================
# REPORT: PNK
# =========================================================
class ReportStockPickingPNKXlsx(models.AbstractModel, StockPickingXlsxMixin):
    _name = "report.somed_stock_documents.report_stock_picking_pnk_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "PNK XLSX"

    def generate_xlsx_report(self, workbook, data, docs):
        self._generate(workbook, data, docs, is_pnk=True)


# =========================================================
# REPORT: PXK
# =========================================================
class ReportStockPickingPXKXlsx(models.AbstractModel, StockPickingXlsxMixin):
    _name = "report.somed_stock_documents.report_stock_picking_pxk_xlsx"
    _inherit = "report.report_xlsx.abstract"
    _description = "PXK XLSX"

    def generate_xlsx_report(self, workbook, data, docs):
        self._generate(workbook, data, docs, is_pnk=False)
