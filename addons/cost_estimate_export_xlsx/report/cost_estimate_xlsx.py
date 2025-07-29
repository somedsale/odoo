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
            'font_name': 'Times New Roman', 'font_size': 11
        })
        info_format = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'font_name': 'Times New Roman', 'font_size': 11
        })
        table_header_format = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#DDEBF7', 'font_name': 'Times New Roman', 'font_size': 11
        })
        parent_left = workbook.add_format({
            'bold': True, 'align': 'left', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        parent_center = workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        parent_money = workbook.add_format({
            'bold': True, 'num_format': '#,##0', 'align': 'right', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        child_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1,  
            'font_name': 'Times New Roman', 'font_size': 11
        })
        child_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1, 
            'font_name': 'Times New Roman', 'font_size': 11
        })
        child_money = workbook.add_format({
            'num_format': '#,##0', 'align': 'right', 'border': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        info_format_money = workbook.add_format({
            'num_format': '#,##0', 'align': 'right', 'valign': 'vcenter',
            'font_name': 'Times New Roman', 'font_size': 11
        })

        # ==== Nét đứt cho dòng con ====
        dashed_left = workbook.add_format({
            'align': 'left', 'valign': 'vcenter',
            'border': 1,
            'top': 3,
            'bottom': 3,  # 3 = dashed
            'left': 1,
            'right': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        dashed_center = workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'border': 1,
            'top': 3,
            'bottom': 3,  # 3 = dashed
            'left': 1,
            'right': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })
        dashed_money = workbook.add_format({
            'align': 'right', 'valign': 'vcenter',
            'num_format': '#,##0', 'border': 1,
            'top': 3,
            'bottom': 3,  # 3 = dashed
            'left': 1,
            'right': 1,
            'font_name': 'Times New Roman', 'font_size': 11
        })

        for estimate in cost_estimates:
            sheet.set_column('A:A', 5)
            sheet.set_column('B:B', 40)
            sheet.set_column('C:C', 10)
            sheet.set_column('D:D', 15)
            sheet.set_column('E:E', 25)
            sheet.set_column('F:F', 25)
            sheet.hide_gridlines(2)
            sheet.set_row(0, 30)
            sheet.set_row(1, 30)
            sheet.merge_range('A1:F2', 'DỰ TOÁN CHI PHÍ', title_format)
            row = 2

            sheet.write(row, 1, 'Tên dự toán:', header_format)
            sheet.write(row, 2, estimate.name or '', info_format)
            row += 1

            sheet.write(row, 1, 'Dự án:', header_format)
            sheet.write(row, 2, estimate.project_id.name or '', info_format)
            row += 1

            sheet.write(row, 1, 'Đơn hàng:', header_format)
            sheet.write(row, 2, estimate.sale_order_id.name or '', info_format)
            row += 1

            sheet.write(row, 1, 'Tổng chi phí:', header_format)
            sheet.write(row, 2, estimate.total_cost or 0.0, info_format_money)
            row += 2

            # Header bảng
            headers = ['STT', 'Tên SP/DV', 'Số lượng', 'Đơn vị', 'Đơn giá (đ)', 'Thành tiền (đ)']
            for col, header in enumerate(headers):
                sheet.write(row, col, header, table_header_format)
            row += 1

            stt = 1 
            for line in estimate.line_ids:
                # Dòng cha
                sheet.write(row, 0, stt, parent_center)
                sheet.write(row, 1, line.product_id.name or 'Không có mô tả', parent_left)
                sheet.write(row, 2, line.quantity or 0.0, parent_center)
                sheet.write(row, 3, line.unit.name or '', parent_center)
                sheet.write(row, 4, line.price_unit or 0.0, parent_money)
                sheet.write(row, 5, line.price_subtotal or 0.0, parent_money)
                row += 1
                stt += 1

                if line.product_type != 'service':
                    # a) Vật liệu
                    if line.material_line_ids:
                        sheet.merge_range(row, 1, row, 2, "a) Vật liệu", dashed_left)
                        sheet.merge_range(row, 3, row, 5, line.material_total_cost, dashed_money)
                        row += 1
                        for material in line.material_line_ids:
                            sheet.write(row, 1, material.material_id.name or '', dashed_left)
                            sheet.write(row, 2, material.quantity, dashed_center)
                            sheet.write(row, 3, material.unit.name or '', dashed_center)
                            sheet.write(row, 4, material.price_unit, dashed_money)
                            sheet.write(row, 5, material.price_total, dashed_money)
                            row += 1

                    # b) Nhân công
                    labor_expenses = line.expense_line_ids.filtered(lambda e: e.type == 'labor')
                    if labor_expenses:
                        sheet.merge_range(row, 1, row, 2, "b) Nhân công", dashed_left)
                        sheet.merge_range(row, 3, row, 5, line.labor_total_cost, dashed_money)
                        row += 1
                        for labor in labor_expenses:
                            sheet.write(row, 1, labor.expense_id.name or '', dashed_left)
                            sheet.write(row, 2, labor.quantity or 1, dashed_center)
                            sheet.write(row, 3, labor.unit.name or '', dashed_center)
                            sheet.write(row, 4, labor.price_unit, dashed_money)
                            sheet.write(row, 5, labor.price_total, dashed_money)
                            row += 1

                    # c) Máy móc
                    equipment_expenses = line.expense_line_ids.filtered(lambda e: e.type == 'equipment')
                    if equipment_expenses:
                        sheet.merge_range(row, 1, row, 2, "c) Máy móc", dashed_left)
                        sheet.merge_range(row, 3, row, 5, line.equipment_total_cost, dashed_money)
                        row += 1
                        for equip in equipment_expenses:
                            sheet.write(row, 1, equip.expense_id.name or '', dashed_left)
                            sheet.write(row, 2, equip.quantity or 1, dashed_center)
                            sheet.write(row, 3, equip.unit.name or '', dashed_center)
                            sheet.write(row, 4, equip.price_unit, dashed_money)
                            sheet.write(row, 5, equip.price_total, dashed_money)
                            row += 1
