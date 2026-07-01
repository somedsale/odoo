from odoo import models, fields
import base64
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image

from PIL import Image as PILImage


class ExportExcelWizard(models.TransientModel):
    _name = 'export.excel.wizard'
    _description = 'Export Excel Wizard'

    def export_to_excel(self):
        sale_orders = self.env['sale.order'].browse(self._context.get('active_ids', []))
        if not sale_orders:
            return False

        wb = Workbook()
        ws = wb.active
        ws.title = "Báo Giá"
        ws.sheet_view.showGridLines = False

        # =========================
        # Styles
        # =========================
        font_title = Font(name='Times New Roman', size=18, bold=True)
        font_header = Font(name='Times New Roman', size=12, bold=True)
        font_normal = Font(name='Times New Roman', size=11)
        font_bold = Font(name='Times New Roman', size=11, bold=True)
        font_italic = Font(name='Times New Roman', size=11, italic=True)
        font_spec = Font(name='Times New Roman', size=10, italic=True, color='555555')
        font_company = Font(name='Times New Roman', size=12, bold=True, italic=True)
        font_company_info = Font(name='Times New Roman', size=11, italic=True)
        font_blue = Font(name='Times New Roman', size=13, bold=True, color='27B1FC')
        font_sign = Font(name='Times New Roman', size=11, bold=True, italic=True)

        align_center = Alignment(horizontal='center', vertical='center', wrap_text=True)
        align_left = Alignment(horizontal='left', vertical='center', wrap_text=True)
        align_right = Alignment(horizontal='right', vertical='center', wrap_text=True)
        align_top_left = Alignment(horizontal='left', vertical='top', wrap_text=True)
        align_top_center = Alignment(horizontal='center', vertical='top', wrap_text=True)
        align_left_no_wrap = Alignment(horizontal='left', vertical='center', wrap_text=False)

        thin_side = Side(style='thin', color='000000')
        dashed_side = Side(style='dashed', color='888888')

        border_all = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side,
        )

        border_spec = Border(
            left=thin_side,
            right=thin_side,
            top=dashed_side,
            bottom=dashed_side,
        )

        fill_header = PatternFill(start_color='E9EEF5', end_color='E9EEF5', fill_type='solid')
        fill_section = PatternFill(start_color='DFE7F2', end_color='DFE7F2', fill_type='solid')
        fill_summary = PatternFill(start_color='F3F0E7', end_color='F3F0E7', fill_type='solid')
        fill_spec = PatternFill(start_color='FCFCFC', end_color='FCFCFC', fill_type='solid')

        current_row = 1
        first_doc = sale_orders[:1]

        def set_row_height(row, height):
            ws.row_dimensions[row].height = height

        def merge_row_text(row, start_col, end_col, value, font=None, alignment=None, border=None, fill=None):
            ws.merge_cells(start_row=row, start_column=start_col, end_row=row, end_column=end_col)
            cell = ws.cell(row=row, column=start_col)
            cell.value = value
            if font:
                cell.font = font
            if alignment:
                cell.alignment = alignment
            if border or fill:
                for c in range(start_col, end_col + 1):
                    if border:
                        ws.cell(row=row, column=c).border = border
                    if fill:
                        ws.cell(row=row, column=c).fill = fill
            return cell

        def apply_row_style(row, start_col, end_col, font=None, alignment=None, border=None, fill=None):
            for c in range(start_col, end_col + 1):
                cell = ws.cell(row=row, column=c)
                if font:
                    cell.font = font
                if alignment:
                    cell.alignment = alignment
                if border:
                    cell.border = border
                if fill:
                    cell.fill = fill

        def money_format(cell):
            cell.number_format = '#,##0'

        def qty_format(cell):
            cell.number_format = '#,##0.##'

        def get_product_name(line):
            return line.product_display_name or line.product_id.name or ""

        def get_spec_text(line):
            """
            Làm giống PDF:
            - Tên sản phẩm lấy từ product_display_name / product_id.name.
            - Dòng diễn giải / thông số lấy từ line.name.
            - Nếu line.name trùng tên sản phẩm thì không sinh dòng thông số.
            """
            product_name = (get_product_name(line) or "").strip()
            line_name = (line.name or "").strip()

            if line_name and line_name != product_name:
                return line_name

            return ""

        def safe_get(record, field_name, default=""):
            if record and field_name in record._fields:
                return getattr(record, field_name) or default
            return default

        for doc_index, doc in enumerate(sale_orders, start=1):
            if doc_index > 1:
                current_row += 3

            company = doc.company_id

            # PDF đang ưu tiên doc.user_id nếu người tạo/sửa là cùng user,
            # ngược lại lấy write_uid. Excel cũng lấy theo cách này để đồng bộ PDF.
            sale_user = (
                doc.user_id
                if doc.user_id and doc.write_uid and doc.user_id.id == doc.write_uid.id
                else doc.write_uid
            )

            sale_user_name = sale_user.name if sale_user else ""
            sale_user_email = sale_user.email if sale_user else ""
            sale_user_phone = (
                safe_get(sale_user, "mobile_phone")
                or safe_get(sale_user, "mobile")
                or safe_get(sale_user, "phone")
                or (sale_user.partner_id.mobile or sale_user.partner_id.phone or "" if sale_user and sale_user.partner_id else "")
            )
            sale_user_address = ""
            if sale_user and sale_user.address_id and sale_user.address_id.contact_address:
                sale_user_address = (
                    sale_user.address_id.contact_address
                    .replace(sale_user.address_id.complete_name or "", "")
                    .strip()
                )

            # =========================
            # Dynamic columns
            # =========================
            headers = ["STT", "Sản phẩm", "Thông số"]

            if doc.is_show_image:
                headers.append("Ảnh")

            if doc.is_show_ma_sp:
                headers.append("Mã SP")

            headers.extend(["Xuất xứ", "Đơn vị", "Khối lượng"])

            if doc.is_show_chi_phi_nhan_cong:
                headers.append("Chi phí nhân công")

            headers.extend(["Đơn giá", "Thành tiền", "Ghi chú"])
            total_cols = len(headers)

            # =========================
            # Column map
            # =========================
            col_no = 1
            stt_col = col_no
            col_no += 1

            product_col = col_no
            col_no += 1

            spec_col = col_no
            col_no += 1

            image_col = None
            if doc.is_show_image:
                image_col = col_no
                col_no += 1

            ma_sp_col = None
            if doc.is_show_ma_sp:
                ma_sp_col = col_no
                col_no += 1

            xuatxu_col = col_no
            col_no += 1

            uom_col = col_no
            col_no += 1

            qty_col = col_no
            col_no += 1

            labor_col = None
            if doc.is_show_chi_phi_nhan_cong:
                labor_col = col_no
                col_no += 1

            price_col = col_no
            col_no += 1

            subtotal_col = col_no
            col_no += 1

            note_col = col_no

            # =========================
            # Column widths
            # =========================
            widths = []
            widths.append(5.5)   # STT
            widths.append(34)    # Sản phẩm
            widths.append(38)    # Thông số

            if doc.is_show_image:
                widths.append(11)   # Ảnh

            if doc.is_show_ma_sp:
                widths.append(13)   # Mã SP

            widths.extend([
                11,    # Xuất xứ
                8.5,   # Đơn vị
                9.5,   # Khối lượng
            ])

            if doc.is_show_chi_phi_nhan_cong:
                widths.append(14)   # Chi phí nhân công

            widths.extend([
                14,    # Đơn giá
                16,    # Thành tiền
                14,    # Ghi chú
            ])

            for i, width in enumerate(widths, start=1):
                ws.column_dimensions[get_column_letter(i)].width = width

            # =========================
            # Company header
            # =========================
            if company.logo:
                try:
                    logo_data = base64.b64decode(company.logo)
                    img = PILImage.open(BytesIO(logo_data))
                    img = img.convert('RGB')
                    img_width, img_height = img.size
                    new_width = 220
                    scale = new_width / img_width
                    img = img.resize((new_width, int(img_height * scale)))
                    img_io = BytesIO()
                    img.save(img_io, format='PNG')
                    img_io.seek(0)
                    logo = Image(img_io)
                    ws.add_image(logo, f'A{current_row}')
                    ws.merge_cells(
                        start_row=current_row,
                        start_column=1,
                        end_row=current_row + 3,
                        end_column=min(4, total_cols)
                    )
                except Exception:
                    pass

            for r in range(current_row, current_row + 4):
                set_row_height(r, 22)

            right_start = max(5, total_cols - 4)
            merge_row_text(
                current_row, right_start, total_cols,
                "CÔNG TY TNHH GIẢI PHÁP KỸ THUẬT Y TẾ MIỀN NAM",
                font=font_company, alignment=align_right
            )
            merge_row_text(
                current_row + 1, right_start, total_cols,
                "Phone: (+84) 932.760.599",
                font=font_company_info, alignment=align_right
            )
            merge_row_text(
                current_row + 2, right_start, total_cols,
                "sales@somed.vn",
                font=font_company_info, alignment=align_right
            )
            merge_row_text(
                current_row + 3, right_start, total_cols,
                "www.somed.vn",
                font=font_company_info, alignment=align_right
            )

            for col in range(1, total_cols + 1):
                ws.cell(row=current_row + 3, column=col).border = Border(bottom=thin_side)

            current_row += 5

            # =========================
            # Title
            # =========================
            merge_row_text(
                current_row, 1, total_cols,
                "BẢNG BÁO GIÁ",
                font=font_title, alignment=align_center
            )
            set_row_height(current_row, 30)
            current_row += 1

            if doc.x_project_name:
                merge_row_text(
                    current_row, 1, max(1, total_cols // 2),
                    f"Dự án: {doc.x_project_name}",
                    font=font_normal, alignment=align_left
                )

            merge_row_text(
                current_row, max(1, total_cols - 2), total_cols,
                doc.name or "",
                font=font_blue, alignment=align_right
            )
            set_row_height(current_row, 22)
            current_row += 2

            # =========================
            # Customer / employee info
            # =========================
            left_label_col = 1
            left_value_start = 2

            right_label_col = max(4, total_cols // 2 + 1)
            right_value_start = right_label_col + 1
            if right_value_start > total_cols:
                right_label_col = total_cols - 1
                right_value_start = total_cols

            customer_address = (
                (doc.partner_id.contact_address or "")
                .replace(doc.partner_id.name or "", "")
                .strip()
            )

            partner_phone = (
                doc.partner_contact_id.phone
                if doc.partner_contact_id and doc.partner_contact_id.phone
                else doc.partner_id.phone or ""
            )
            partner_email = (
                doc.partner_contact_id.email
                if doc.partner_contact_id and doc.partner_contact_id.email
                else doc.partner_id.email or ""
            )

            if doc.partner_contact_id:
                partner_phone_label = "Người liên hệ:"
                partner_phone_value = "%s - %s" % (
                    doc.partner_contact_id.name or "",
                    doc.partner_contact_id.phone or "",
                )
            else:
                partner_phone_label = "Điện thoại:"
                partner_phone_value = partner_phone

            info_rows = [
                ("Khách hàng:", doc.partner_id.name or "", "Nhân viên kinh doanh:", sale_user_name),
                ("Địa chỉ:", customer_address, "Địa chỉ:", sale_user_address),
                (partner_phone_label, partner_phone_value, "Điện thoại:", sale_user_phone),
                ("Email:", partner_email, "Email:", sale_user_email),
            ]

            for left_label, left_value, right_label, right_value in info_rows:
                ws.cell(row=current_row, column=left_label_col).value = left_label
                ws.cell(row=current_row, column=left_label_col).font = font_bold
                ws.cell(row=current_row, column=left_label_col).alignment = align_left_no_wrap

                merge_row_text(
                    current_row,
                    left_value_start,
                    right_label_col - 1,
                    left_value,
                    font=font_normal,
                    alignment=align_left
                )

                ws.cell(row=current_row, column=right_label_col).value = right_label
                ws.cell(row=current_row, column=right_label_col).font = font_bold
                ws.cell(row=current_row, column=right_label_col).alignment = align_left_no_wrap

                merge_row_text(
                    current_row,
                    right_value_start,
                    total_cols,
                    right_value,
                    font=font_normal,
                    alignment=align_left
                )

                set_row_height(current_row, 22)
                current_row += 1

            current_row += 1

            # =========================
            # Intro
            # =========================
            intro_1 = (
                "Lời đầu tiên Công ty TNHH giải pháp kỹ thuật Y tế Miền Nam xin gửi Quý khách hàng "
                "lời chúc sức khỏe và lời chào trân trọng nhất!"
            )
            intro_2 = (
                "Công ty TNHH giải pháp kỹ thuật Y tế Miền Nam xin gửi Quý khách hàng bảng báo giá "
                "sản phẩm, vật tư theo yêu cầu từ Quý khách hàng, cụ thể như sau:"
            )

            merge_row_text(current_row, 1, total_cols, intro_1, font=font_normal, alignment=align_left)
            set_row_height(current_row, 30)
            current_row += 1

            merge_row_text(current_row, 1, total_cols, intro_2, font=font_normal, alignment=align_left)
            set_row_height(current_row, 30)
            current_row += 1

            # =========================
            # Table header
            # =========================
            header_row = current_row
            for col_idx, header in enumerate(headers, start=1):
                cell = ws.cell(row=header_row, column=col_idx)
                cell.value = header
                cell.font = font_header
                cell.alignment = align_center
                cell.border = border_all
                cell.fill = fill_header
            set_row_height(header_row, 32)
            current_row += 1

            # =========================
            # Product lines
            # =========================
            stt = 0
            sttLM = 0

            for line in doc.order_line:
                if line.display_type == 'line_section':
                    sttLM += 1
                    stt = 0

                    roman = doc.int_to_roman(sttLM)

                    ws.cell(row=current_row, column=stt_col).value = roman
                    ws.cell(row=current_row, column=stt_col).font = font_header
                    ws.cell(row=current_row, column=stt_col).alignment = align_center
                    ws.cell(row=current_row, column=stt_col).border = border_all
                    ws.cell(row=current_row, column=stt_col).fill = fill_section

                    merge_row_text(
                        current_row, product_col, total_cols, line.name or "",
                        font=font_header, alignment=align_left, border=border_all, fill=fill_section
                    )
                    apply_row_style(
                        current_row, product_col, total_cols,
                        font=font_header, alignment=align_left, border=border_all, fill=fill_section
                    )

                    set_row_height(current_row, 26)
                    current_row += 1
                    continue

                if line.display_type == 'line_note':
                    ws.cell(row=current_row, column=stt_col).value = ""
                    ws.cell(row=current_row, column=stt_col).font = font_italic
                    ws.cell(row=current_row, column=stt_col).alignment = align_top_center
                    ws.cell(row=current_row, column=stt_col).border = border_all
                    ws.cell(row=current_row, column=stt_col).fill = fill_spec

                    merge_row_text(
                        current_row, product_col, total_cols, line.name or "",
                        font=font_italic, alignment=align_top_left, border=border_all, fill=fill_spec
                    )
                    apply_row_style(
                        current_row, product_col, total_cols,
                        font=font_italic, alignment=align_top_left, border=border_all, fill=fill_spec
                    )

                    set_row_height(current_row, 32)
                    current_row += 1
                    continue

                if line.display_type:
                    continue

                stt += 1
                spec_text = get_spec_text(line)

                # Main row
                ws.cell(row=current_row, column=stt_col).value = stt
                ws.cell(row=current_row, column=stt_col).font = font_bold
                ws.cell(row=current_row, column=stt_col).alignment = align_center
                ws.cell(row=current_row, column=stt_col).border = border_all

                ws.cell(row=current_row, column=product_col).value = get_product_name(line)
                ws.cell(row=current_row, column=product_col).font = font_bold
                ws.cell(row=current_row, column=product_col).alignment = align_top_left
                ws.cell(row=current_row, column=product_col).border = border_all

                ws.cell(row=current_row, column=spec_col).value = spec_text
                ws.cell(row=current_row, column=spec_col).font = font_spec if spec_text else font_normal
                ws.cell(row=current_row, column=spec_col).alignment = align_top_left
                ws.cell(row=current_row, column=spec_col).border = border_all

                if image_col:
                    ws.cell(row=current_row, column=image_col).alignment = align_center
                    ws.cell(row=current_row, column=image_col).border = border_all

                if ma_sp_col:
                    ws.cell(row=current_row, column=ma_sp_col).value = line.product_id.default_code or ""
                    ws.cell(row=current_row, column=ma_sp_col).font = font_normal
                    ws.cell(row=current_row, column=ma_sp_col).alignment = align_center
                    ws.cell(row=current_row, column=ma_sp_col).border = border_all

                ws.cell(row=current_row, column=xuatxu_col).value = line.x_xuatxu or ""
                ws.cell(row=current_row, column=xuatxu_col).font = font_normal
                ws.cell(row=current_row, column=xuatxu_col).alignment = align_center
                ws.cell(row=current_row, column=xuatxu_col).border = border_all

                ws.cell(row=current_row, column=uom_col).value = line.product_uom.name or ""
                ws.cell(row=current_row, column=uom_col).font = font_normal
                ws.cell(row=current_row, column=uom_col).alignment = align_center
                ws.cell(row=current_row, column=uom_col).border = border_all

                ws.cell(row=current_row, column=qty_col).value = line.product_uom_qty or 0.0
                ws.cell(row=current_row, column=qty_col).font = font_normal
                ws.cell(row=current_row, column=qty_col).alignment = align_center
                ws.cell(row=current_row, column=qty_col).border = border_all
                qty_format(ws.cell(row=current_row, column=qty_col))

                if labor_col:
                    ws.cell(row=current_row, column=labor_col).value = line.x_chi_phi_nhan_cong or 0.0
                    ws.cell(row=current_row, column=labor_col).font = font_normal
                    ws.cell(row=current_row, column=labor_col).alignment = align_right
                    ws.cell(row=current_row, column=labor_col).border = border_all
                    money_format(ws.cell(row=current_row, column=labor_col))

                price_cell = ws.cell(row=current_row, column=price_col)
                if "formatted_price" in line._fields and line.formatted_price:
                    # PDF đang hiển thị line.formatted_price, nên Excel cũng ưu tiên field này.
                    price_cell.value = line.formatted_price
                else:
                    price_cell.value = line.price_unit or 0.0
                    money_format(price_cell)
                price_cell.font = font_normal
                price_cell.alignment = align_right
                price_cell.border = border_all

                ws.cell(row=current_row, column=subtotal_col).value = line.price_subtotal or 0.0
                ws.cell(row=current_row, column=subtotal_col).font = font_normal
                ws.cell(row=current_row, column=subtotal_col).alignment = align_right
                ws.cell(row=current_row, column=subtotal_col).border = border_all
                money_format(ws.cell(row=current_row, column=subtotal_col))

                ws.cell(row=current_row, column=note_col).value = line.x_note or ""
                ws.cell(row=current_row, column=note_col).font = font_normal
                ws.cell(row=current_row, column=note_col).alignment = align_top_left
                ws.cell(row=current_row, column=note_col).border = border_all

                product_name_line_count = len(str(get_product_name(line) or "").splitlines()) or 1
                spec_line_count = len(str(spec_text or "").splitlines()) or 1
                note_line_count = len(str(line.x_note or "").splitlines()) or 1
                text_line_count = max(product_name_line_count, spec_line_count, note_line_count)
                row_height = max(28, min(120, 18 * text_line_count))

                if image_col and line.product_id.image_1920:
                    try:
                        img_data = base64.b64decode(line.product_id.image_1920)
                        pimg = PILImage.open(BytesIO(img_data))
                        pimg = pimg.convert('RGB')
                        pimg.thumbnail((70, 70))

                        img_io = BytesIO()
                        pimg.save(img_io, format='PNG')
                        img_io.seek(0)

                        xl_img = Image(img_io)
                        ws.add_image(xl_img, f"{get_column_letter(image_col)}{current_row}")
                        row_height = max(row_height, 58)
                    except Exception:
                        pass

                set_row_height(current_row, row_height)
                current_row += 1

            # =========================
            # Summary
            # =========================
            tax_details = {}
            for line in doc.order_line:
                if line.display_type:
                    continue
                for tax in line.tax_id:
                    base = tax_details.get(tax.name, {'base': 0.0, 'amount': 0.0})
                    tax_details[tax.name] = {
                        'base': base['base'] + line.price_subtotal,
                        'amount': base['amount'] + (line.price_subtotal * tax.amount / 100.0),
                    }

            summary_label_end = subtotal_col - 1

            def write_summary_row(label, amount):
                nonlocal current_row

                merge_row_text(
                    current_row, 1, summary_label_end, label,
                    font=font_header, alignment=align_left, border=border_all, fill=fill_summary
                )
                apply_row_style(
                    current_row, 1, summary_label_end,
                    font=font_header, alignment=align_left, border=border_all, fill=fill_summary
                )

                amount_cell = ws.cell(row=current_row, column=subtotal_col)
                amount_cell.value = amount or 0.0
                amount_cell.font = font_header
                amount_cell.alignment = align_right
                amount_cell.border = border_all
                amount_cell.fill = fill_summary
                money_format(amount_cell)

                note_cell = ws.cell(row=current_row, column=note_col)
                note_cell.value = ""
                note_cell.font = font_header
                note_cell.alignment = align_left
                note_cell.border = border_all
                note_cell.fill = fill_summary

                set_row_height(current_row, 24)
                current_row += 1

            write_summary_row("Tổng chưa VAT", doc.amount_untaxed)

            for tax_name, details in tax_details.items():
                write_summary_row(f"VAT {tax_name}", details['amount'])

            write_summary_row("Tổng", doc.amount_total)

            # =========================
            # Amount in words
            # =========================
            merge_row_text(
                current_row, 1, total_cols,
                "Số tiền bằng chữ: %s" % (doc.amount_to_text_vi(doc.amount_total) or ""),
                font=font_header, alignment=align_center
            )
            set_row_height(current_row, 28)
            current_row += 2

            # =========================
            # Commercial conditions
            # =========================
            merge_row_text(
                current_row, 1, total_cols,
                "Điều kiện thương mại:",
                font=font_header, alignment=align_left
            )
            set_row_height(current_row, 22)
            current_row += 1

            line_num = 1
            lines = []

            if doc.is_including_testing:
                lines.append(f"{line_num}. Báo giá đã bao gồm chi phí kiểm định")
                line_num += 1

            lines.append(f"{line_num}. Báo giá đã bao gồm Thuế VAT")
            line_num += 1

            if doc.is_including_installation and doc.is_including_transport:
                lines.append(f"{line_num}. Báo giá đã bao gồm lắp đặt và vận chuyển")
            elif doc.is_including_installation:
                lines.append(f"{line_num}. Báo giá đã bao gồm lắp đặt")
            elif doc.is_including_transport:
                lines.append(f"{line_num}. Báo giá đã bao gồm vận chuyển")
            else:
                lines.append(f"{line_num}. Báo giá chưa bao gồm lắp đặt và vận chuyển")
            line_num += 1

            if doc.x_estimated_delivery_time_id:
                lines.append(f"{line_num}. Thời gian giao hàng: {doc.x_estimated_delivery_time_id.name}")
                line_num += 1

            if doc.x_warranty_duration_id:
                lines.append(f"{line_num}. Thời gian bảo hành: {doc.x_warranty_duration_id.name}")
                line_num += 1

            lines.append(f"{line_num}. Điều khoản thanh toán:")
            payment_terms_num = line_num
            line_num += 1

            if doc.x_payment_method_id:
                lines.append(f"{line_num}. Phương thức thanh toán: {doc.x_payment_method_id.name}")
                line_num += 1

            bank = doc.company_bank_id or (doc.company_id.partner_id.bank_ids and doc.company_id.partner_id.bank_ids[0]) or False
            if bank:
                lines.append(f"    Chủ tài khoản: {bank.acc_holder_name or bank.partner_id.name or ''}")
                lines.append(f"    Số tài khoản: {bank.acc_number or ''}")
                lines.append(f"    Tại Ngân hàng: {bank.bank_id.name or ''}")

            if doc.x_delivery_location:
                lines.append(f"{line_num}. Địa điểm giao hàng: {doc.x_delivery_location}")
                line_num += 1

            if doc.validity_date and doc.date_order:
                lines.append(
                    f"{line_num}. Bảng báo giá có hiệu lực trong vòng {doc.x_quote_valid_until} ngày, "
                    "sau đó có thể được thay đổi mà không thông báo trước."
                )
                line_num += 1

            for item in lines:
                merge_row_text(current_row, 1, total_cols, item, font=font_normal, alignment=align_left)
                set_row_height(current_row, 26)
                current_row += 1

                if item == f"{payment_terms_num}. Điều khoản thanh toán:":
                    merge_row_text(
                        current_row, 1, total_cols,
                        doc.x_custom_payment_terms or "",
                        font=font_normal, alignment=align_left
                    )
                    set_row_height(current_row, 42)
                    current_row += 1

            current_row += 2

            # =========================
            # Sign
            # =========================
            left_end = total_cols // 2
            right_start = left_end + 1

            merge_row_text(
                current_row, 1, left_end,
                "Xác nhận của khách hàng\n(Ký tên, đóng dấu)",
                font=font_italic, alignment=align_center
            )

            merge_row_text(
                current_row, right_start, total_cols,
                "%s\nCÔNG TY TNHH GIẢI PHÁP KỸ THUẬT Y TẾ MIỀN NAM\nPHÒNG KINH DOANH\n\n%s" % (
                    doc.formatted_date or "",
                    sale_user_name or ""
                ),
                font=font_sign, alignment=align_center
            )
            set_row_height(current_row, 110)
            current_row += 1

            # =========================
            # Page setup
            # =========================
            ws.page_setup.orientation = 'landscape'
            ws.page_setup.paperSize = ws.PAPERSIZE_A4
            ws.page_margins.left = 0.25
            ws.page_margins.right = 0.25
            ws.page_margins.top = 0.4
            ws.page_margins.bottom = 0.4
            # Không freeze header để tránh cố định khi kéo scroll trong file Excel.
            ws.freeze_panes = None

        output = BytesIO()
        wb.save(output)
        output.seek(0)

        file_data = base64.b64encode(output.read())
        attachment = self.env['ir.attachment'].create({
            'name': f'sale_order_{first_doc.name}.xlsx',
            'type': 'binary',
            'datas': file_data,
            'res_model': 'sale.order',
            'res_id': first_doc.id,
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }
