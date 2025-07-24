from odoo import models
import base64
from io import BytesIO

class ProposalSheetXlsx(models.AbstractModel):
    _name = 'report.proposal_sheet_xlsx_report.proposal_sheet_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, proposals):

        PAPER_SIZE = 11  # Đổi 9 cho A4, 11 cho A5
        LANDSCAPE = True  # True = Nằm ngang, False = Dọc
        # ====== Định dạng ======
        title_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 24, 'font_name': 'Times New Roman',
        })
        header_format = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman','font_size': 13
        })
        info_format_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman','font_size': 13})
        info_format_right = workbook.add_format({'align': 'right', 'valign': 'vcenter', 'font_name': 'Times New Roman','font_size': 13})

        # Chỉ cho bảng có border
        table_header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1, 'color': '#000000', 'bg_color': '#DDEBF7',
            'font_name': 'Times New Roman', 'font_size': 13
        })
        table_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1, 'font_name': 'Times New Roman', 'font_size': 13})
        table_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1, 'font_name': 'Times New Roman', 'font_size': 13})
        table_money = workbook.add_format({'num_format': '#,##0', 'align': 'right', 'border': 1, 'font_name': 'Times New Roman', 'font_size': 13})

        # Lấy company
        company = proposals[0].company_id if hasattr(proposals[0], 'company_id') else self.env.company

        for proposal in proposals:
            sheet = workbook.add_worksheet(proposal.name[:31])
            sheet.set_column('A:I', 15)  # Set độ rộng cột
            sheet.set_row(0, 30)  # Dòng đầu tiên
            sheet.set_row(1, 30)  # Dòng thứ hai
            sheet.hide_gridlines(2)
            sheet.set_paper(PAPER_SIZE)
            if LANDSCAPE:
                sheet.set_landscape()
            else:
                sheet.set_portrait()
            sheet.fit_to_pages(1, 1)
            sheet.center_horizontally()
            sheet.set_margins(left=0.3, right=0.3, top=0.3, bottom=0.3)

            # ====== Logo công ty ======
            if company.logo:
                image_data = base64.b64decode(company.logo)
                image_file = BytesIO(image_data)
                sheet.insert_image('A1', 'logo.png', {
                    'image_data': image_file,
                    'x_scale': 1.2, 'y_scale': 1.2
                })

            # ====== Tiêu đề ======
            title_text = 'PHIẾU ĐỀ XUẤT VẬT TƯ' if proposal.type == 'material' else 'PHIẾU ĐỀ XUẤT CHI PHÍ'
            sheet.merge_range('A1:H2', title_text, title_format)

            # ====== Thông tin chung ======
            sheet.merge_range('G3:H3', f"Số: {proposal.name or ''}", info_format_right)

            row = 4
            # Dòng 1: CBNV | ..........     PHÒNG BAN: ..........
            sheet.write(row, 0, 'CBNV:', header_format)
            sheet.merge_range(row, 1, row, 3, proposal.requested_by.name or '', info_format_left)
            department_name = ''
            if proposal.requested_by and proposal.requested_by.employee_id and proposal.requested_by.employee_id.department_id:
                department_name = proposal.requested_by.employee_id.department_id.name
            sheet.write(row, 4, 'PHÒNG BAN:', header_format)
            sheet.merge_range(row, 5, row, 7, department_name, info_format_left)
            row += 1

            # Dòng 2: Dùng cho sản phẩm, hạng mục: ......... | Thuộc công trình/hợp đồng/báo giá: ......
            sheet.merge_range(row, 0,row, 1, 'Dùng cho sản phẩm:', header_format)
            sheet.merge_range(row, 2, row, 7, proposal.task_id.name or '', info_format_left)
            row += 1
            sheet.merge_range(row, 0,row, 1, 'Thuộc dự án:', header_format)
            sheet.merge_range(row, 2, row, 7, proposal.project_id.name or '', info_format_left)
            row += 2

            # ====== Header bảng ======
            if proposal.type == 'material':
                headers = ['STT', 'Tên vật tư', 'Đơn vị', 'Số lượng', 'Đơn giá', 'Thành tiền', 'NCC đề xuất', 'Ghi chú']
                for col, head in enumerate(headers):
                    sheet.write(row, col, head, table_header_format)
            else:  # expense
                base_headers = ['STT', 'Tên chi phí', 'Đơn vị', 'Số lượng', 'Đơn giá', 'Thành tiền']
                for col, head in enumerate(base_headers):
                    sheet.write(row, col, head, table_header_format)
                sheet.merge_range(row, 6, row, 7, 'Ghi chú', table_header_format)  
        row += 1

        # ====== Dòng chi tiết ======
        lines = proposal.material_line_ids if proposal.type == 'material' else proposal.expense_line_ids

        for idx, line in enumerate(lines, start=1):
            sheet.write(row, 0, idx, table_center)

            if proposal.type == 'material':
                sheet.write(row, 1, line.material_id.name or '', table_left)
                sheet.write(row, 2, line.unit.name or '', table_center)
                sheet.write(row, 3, line.quantity or 0, table_center)
                sheet.write(row, 4, line.price_unit or 0, table_money)
                sheet.write(row, 5, line.price_total or 0, table_money)
                sheet.write(row, 6, line.proposed_supplier or '', table_left)
                sheet.write(row, 7, line.description or '', table_left)
            else:  # expense
                sheet.write(row, 1, line.expense_id.name or '', table_left)
                sheet.write(row, 2, line.unit.name or '', table_center)
                sheet.write(row, 3, line.quantity or 0, table_center)
                sheet.write(row, 4, line.price_unit or 0, table_money)
                sheet.write(row, 5, line.price_total or 0, table_money)
                sheet.merge_range(row, 6, row, 7, line.description or '', table_left)

            row += 1

        # ====== Tổng cộng ======
        sheet.merge_range(row, 0, row, 4, 'Tổng cộng', table_header_format)
        sheet.merge_range(row, 5, row, 7, proposal.amount_total or 0, table_money)
        row += 1

        # ====== Ghi chú ======
        sheet.write(row, 0, 'Ghi chú:', header_format)
        sheet.merge_range(row, 1, row, 7, proposal.take_note or '', info_format_left)

            # ====== Chỗ ký tên ======
        row += 3
        signature_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'bold': True, 'font_name': 'Times New Roman', 'font_size': 11
        })
        signature_note_format = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'italic': True, 'font_name': 'Times New Roman', 'font_size': 11
        })

        # Hàng ngày tháng
        sheet.merge_range(row, 0, row, 1, '...../...../ 2025', signature_format)
        sheet.merge_range(row, 2, row, 3, '...../...../ 2025', signature_format)
        sheet.merge_range(row, 4, row, 5, '...../...../ 2025', signature_format)
        sheet.merge_range(row, 6, row, 7, '...../...../ 2025', signature_format)
        row += 1

        # Hàng chức danh
        sheet.merge_range(row, 0, row, 1, 'NGƯỜI ĐỀ XUẤT', signature_format)
        sheet.merge_range(row, 2, row, 3, 'TRƯỞNG BỘ PHẬN', signature_format)
        sheet.merge_range(row, 4, row, 5, 'KẾ TOÁN TỔNG HỢP', signature_format)
        sheet.merge_range(row, 6, row, 7, 'GIÁM ĐỐC', signature_format)
        row += 1

        # Hàng chữ ký
        sheet.merge_range(row, 0, row, 1, '(Ký, họ tên)', signature_note_format)
        sheet.merge_range(row, 2, row, 3, '(Ký, họ tên)', signature_note_format)
        sheet.merge_range(row, 4, row, 5, '(Ký, họ tên)', signature_note_format)
        sheet.merge_range(row, 6, row, 7, '(Ký, họ tên)', signature_note_format)
