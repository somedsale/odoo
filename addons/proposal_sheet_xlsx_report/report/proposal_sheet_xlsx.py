from odoo import models
import base64
from io import BytesIO

class ProposalSheetXlsx(models.AbstractModel):
    _name = 'report.proposal_sheet_xlsx_report.proposal_sheet_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, proposals):
        # ====== Định dạng ======
        title_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 14, 'bg_color': '#D9EDF7'
        })
        header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'bg_color': '#27B1FC', 'border': 1
        })
        normal_center = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'border': 1})
        normal_left = workbook.add_format({'align': 'left', 'valign': 'vcenter', 'border': 1})
        money_format = workbook.add_format({'num_format': '#,##0', 'align': 'right', 'border': 1})

        # Lấy company
        company = proposals[0].company_id if hasattr(proposals[0], 'company_id') else self.env.company

        for proposal in proposals:
            sheet = workbook.add_worksheet(proposal.name[:31])
            sheet.set_column('A:H', 18)  # Set độ rộng cột

            # ====== Logo công ty ======
            if company.logo:
                image_data = base64.b64decode(company.logo)
                image_file = BytesIO(image_data)
                sheet.insert_image('A1', 'logo.png', {
                    'image_data': image_file,
                    'x_scale': 4, 'y_scale': 4
                })

            # ====== Tiêu đề ======
            sheet.merge_range('C1:H2', 'PHIẾU ĐỀ XUẤT VẬT TƯ / CHI PHÍ', title_format)

            # ====== Thông tin chung ======
            row = 4
            sheet.write(row, 0, 'Mã phiếu', header_format)
            sheet.write(row, 1, proposal.name or '', normal_left)
            sheet.write(row, 2, 'Ngày', header_format)
            sheet.write(row, 3, str(proposal.create_date.date()), normal_center)
            sheet.write(row, 4, 'Người đề xuất', header_format)
            sheet.write(row, 5, proposal.create_uid.name or '', normal_left)
            row += 2

            # ====== Header bảng ======
            headers = ['STT', 'Tên vật tư / Chi phí', 'Đơn vị', 'Số lượng', 'Đơn giá', 'Thành tiền', 'NCC đề xuất', 'Ghi chú']
            for col, head in enumerate(headers):
                sheet.write(row, col, head, header_format)
            row += 1

            # ====== Dòng chi tiết ======
            lines = proposal.material_line_ids if proposal.type == 'material' else proposal.expense_line_ids
            for idx, line in enumerate(lines, start=1):
                sheet.write(row, 0, idx, normal_center)
                name = line.material_id.name if proposal.type == 'material' else line.expense_id.name
                sheet.write(row, 1, name, normal_left)
                sheet.write(row, 2, line.unit.name or '', normal_center)
                sheet.write(row, 3, line.quantity or 0, normal_center)
                sheet.write(row, 4, line.price_unit or 0, money_format)
                sheet.write(row, 5, line.price_total or 0, money_format)
                sheet.write(row, 6, line.proposed_supplier or '', normal_left)
                sheet.write(row, 7, line.description or '', normal_left)
                row += 1

            # ====== Tổng cộng ======
            sheet.merge_range(row, 0, row, 4, 'Tổng cộng', header_format)
            sheet.write(row, 5, proposal.amount_total or 0, money_format)

            # ====== Chỗ ký tên ======
            row += 3
            sheet.write(row, 1, 'Người đề xuất', normal_center)
            sheet.write(row, 3, 'Người duyệt', normal_center)
            sheet.write(row, 5, 'Người thực hiện', normal_center)
