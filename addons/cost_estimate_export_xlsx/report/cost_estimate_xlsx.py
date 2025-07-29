from odoo import models

class CostEstimateXlsx(models.AbstractModel):
    _name = 'report.cost_estimate_xlsx_report.cost_estimate_xlsx'
    _inherit = 'report.report_xlsx.abstract'

    def generate_xlsx_report(self, workbook, data, cost_estimates):
        sheet = workbook.add_worksheet('Chi tiết dự toán')
        row = 0

        # ====== Định dạng ======
        title_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter',
            'font_size': 24, 'font_name': 'Times New Roman',
        })
        header_format = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter',
            'font_name': 'Times New Roman', 'font_size': 13
        })
        info_format_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman', 'font_size': 13
        })
        table_header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'color': '#000000', 'bg_color': '#DDEBF7',
            'font_name': 'Times New Roman', 'font_size': 13
        })

        # === Format cho dòng cha (đậm, to hơn) ===
        parent_left = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 14
        })
        parent_center = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 14
        })
        parent_money = workbook.add_format({
            'bold': True, 'num_format': '#,##0', 'align': 'right', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 14
        })

        # === Format cho dòng con (nhỏ hơn, không đậm) ===
        child_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 12
        })
        child_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 12
        })
        child_money = workbook.add_format({
            'num_format': '#,##0', 'align': 'right', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 12
        })

        for estimate in cost_estimates:
            sheet.set_column('A:I', 15)
            sheet.merge_range('A1:E2', 'DỰ TOÁN CHI PHÍ', title_format)
            row = 2

            sheet.write(row, 0, 'Tên dự toán:', header_format)
            sheet.write(row, 1, estimate.name or '', info_format_left)
            row += 1

            sheet.write(row, 0, 'Dự án:', header_format)
            sheet.write(row, 1, estimate.project_id.name or '', info_format_left)
            row += 1

            sheet.write(row, 0, 'Đơn hàng:', header_format)
            sheet.write(row, 1, estimate.sale_order_id.name or '', info_format_left)
            row += 1

            sheet.write(row, 0, 'Tổng chi phí:', header_format)
            sheet.write(row, 1, estimate.total_cost or 0.0, child_money)
            row += 2

            headers = ['Tên SP/DV', 'Số lượng', 'Đơn vị', 'Đơn giá', 'Thành tiền']
            for col, header in enumerate(headers):
                sheet.write(row, col, header, table_header_format)
            row += 1

            for line in estimate.line_ids:
                if line.material_line_ids or line.expense_line_ids:
                    # Dòng cha
                    sheet.write(row, 0, line.product_id.name or 'Không có mô tả', parent_left)
                    sheet.write(row, 1, line.quantity or 0.0, parent_center)
                    sheet.write(row, 2, line.unit.name or '', parent_center)
                    sheet.write(row, 3, line.price_unit or 0.0, parent_money)
                    sheet.write(row, 4, line.price_subtotal or 0.0, parent_money)
                    row += 1

                    # Dòng con
                    if line.product_type != 'service':
                        for material in line.material_line_ids:
                            sheet.write(row, 0, material.material_id.name or '', child_left)
                            sheet.write(row, 1, material.quantity, child_center)
                            sheet.write(row, 2, material.unit.name or '', child_center)
                            sheet.write(row, 3, material.price_unit, child_money)
                            sheet.write(row, 4, material.price_total, child_money)
                            row += 1
                    else:
                        for expense in line.expense_line_ids:
                            sheet.write(row, 0, expense.expense_id.name or '', child_left)
                            sheet.write(row, 1, 1, child_center)
                            sheet.write(row, 2, expense.unit.name or '', child_center)
                            sheet.write(row, 3, expense.price_unit, child_money)
                            sheet.write(row, 4, expense.price_total, child_money)
                            row += 1
