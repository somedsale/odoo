from odoo import models
import base64
from io import BytesIO
from datetime import datetime

class AccountReceiptXlsx(models.AbstractModel):
    _name = 'report.account_receipt_xlsx_report.account_receipt_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, records):
        sheet = workbook.add_worksheet("Phiếu thu")
        sheet.set_zoom(110)

        sheet.set_column('A:D', 25)
        # sheet.set_column('D:D', 30)
        sheet.hide_gridlines(2)
        sheet.set_paper(11)         # A5
        sheet.set_landscape()
        sheet.fit_to_pages(1, 1)

        # --- Style ---
        title = workbook.add_format({'bold': True, 'align': 'center', 'valign': 'vcenter',
                                     'font_size': 18, 'font_name': 'Times New Roman'})
        header_left = workbook.add_format({'align': 'left', 'font_size': 12, 'font_name': 'Times New Roman'})
        header_badge = workbook.add_format({
            'align': 'center',
            'valign': 'vcenter',
            'border': 1,
            'font_size': 12,
            'font_name': 'Times New Roman',
            'bold': True,
            'italic': True,
        })
        normal_left = workbook.add_format({'align': 'left', 'font_size': 13, 'font_name': 'Times New Roman'})
        italic_center = workbook.add_format({'italic': True, 'bold': True, 'align': 'center', 'font_size': 13, 'font_name': 'Times New Roman'})
        italic_center_label = workbook.add_format({'italic': True,  'align': 'center', 'font_size': 13, 'font_name': 'Times New Roman'})
        date_format = workbook.add_format({'italic': True,  'align': 'center', 'font_size': 13, 'font_name': 'Times New Roman'})
        label_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 13,
            'font_name': 'Times New Roman',
        })

        value_format = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 13,
            'font_name': 'Times New Roman',
            'bottom': 7,   # gạch chân dưới
        })
        value_money_format = workbook.add_format({
            'bold': True,
            'align': 'left',
            'valign': 'vcenter',
            'font_size': 13,
            'font_name': 'Times New Roman',
            'bottom': 7,   # gạch chân dưới
        })
        # --- Header công ty ---
        row=0
        company = records[0].company_id if hasattr(records[0], 'company_id') else self.env.company
        sheet.merge_range('A1:C1', company.name or "CÔNG TY TNHH ...", header_left)
        row += 1
        sheet.merge_range('A2:C2', company.street or "", header_left)
        row += 1
        sheet.merge_range('A3:C3', f"MST: {company.vat or ''}", header_left)
        row += 1
        sheet.merge_range('D2:D3', "LƯU HÀNH NỘI BỘ", header_badge)

        sheet.merge_range('B5:C5',"PHIẾU THU", title)
        row += 1
        sheet.write('D5', "Quyển số: .....................", normal_left)
        row += 1


        # --- Ngày tháng ---
        today = datetime.today().strftime("Ngày %d tháng %m năm %Y")
        sheet.merge_range('B6:C6', today, italic_center)
        sheet.write('D6', "Số: ...............................", normal_left)
        row +=2
        # Họ tên người nộp tiền
        sheet.write(row, 0, "Họ tên người nộp tiền:", label_format)
        receipter_name = records[0].create_uid.name if records[0].create_uid else ""
        sheet.merge_range(row, 1, row, 3, receipter_name, value_format)
        row += 1

        # Địa chỉ
        sheet.write(row, 0, "Địa chỉ:", label_format)
        receipt_address = records[0].create_uid.contact_address if records[0].create_uid else ""
        sheet.merge_range(row, 1, row, 3, receipt_address, value_format)
        row += 1

        # Lý do chi
        sheet.write(row, 0, "Lý do chi:", label_format)
        reason = records[0].note or ""
        sheet.merge_range(row, 1, row, 3, reason, value_format)
        row += 1

        # Hợp đồng / BG
        sheet.write(row, 0, "Thuộc HĐ/BG:", label_format)
        project = records[0].project_id
       

        if project:
            # Tìm hợp đồng có project_id trùng
            contract = self.env['supplier.contract'].search([('project_id', '=', project.id)], limit=1)
        if contract:
            contract_name = contract.name
        else:
            contract_name = ""
        sheet.merge_range(row, 1, row, 3, contract_name, value_format)
        row += 1
        # Số tiền
        sheet.write(row, 0, "Số tiền:", label_format)
        amount = records[0].amount or 0.0
        # currency = records[0].currency_id.symbol or "đ"
        currency = "đ"

        sheet.merge_range(row, 1, row, 3, f"{amount:,.0f} {currency}", value_money_format)
        row += 1

        sheet.write(row, 0, "Số tiền bằng chữ:", label_format)
        amount_words = records[0].amount_in_words or ""
        sheet.merge_range(row, 1, row, 3, amount_words, value_format)
        row += 1

        sheet.write(row, 0, "Chứng từ kèm theo:", label_format)
        sheet.merge_range(row, 1, row, 3, "", value_format)
        row += 1
        # today = datetime.today().strftime("Ngày %d tháng %m năm %Y")
        sheet.merge_range(row, 2, row, 3, today, date_format)
        row += 1
        # --- Chữ ký ---
        sheet.write(row, 0, "Người nhận tiền", italic_center)
        sheet.write(row, 1, "Kế toán tổng hợp", italic_center)
        sheet.write(row, 2, "Thủ quỹ", italic_center)
        sheet.write(row, 3, "Giám đốc", italic_center); row += 1

        sheet.write(row, 0, "(Ký, họ tên)", italic_center_label)
        sheet.write(row, 1, "(Ký, họ tên)", italic_center_label)
        sheet.write(row, 2, "(Ký, họ tên)", italic_center_label)
        sheet.write(row, 3, "(Ký, họ tên, đóng dấu)", italic_center_label)
        row += 4
        sheet.write(row, 0, "Đã thu đủ tiền:", label_format)
        sheet.merge_range(row, 1, row, 3, amount_words, value_format)

    
