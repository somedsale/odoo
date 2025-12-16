# -*- coding: utf-8 -*-
from io import BytesIO
import base64
import xlwt
import calendar
from datetime import date as pydate

from odoo import fields, models, api, _
from odoo.exceptions import UserError


class StockReportWizard(models.TransientModel):
    """
    StockReportWizard is a transient model used to generate a stock report card
    within a specified date range and location. It provides the functionality
    to export the report in PDF and Excel formats.
    """
    _name = 'stock.report.wizard'
    _description = "Stock Report Card"

    # --------- FILTER KỲ ----------
    period_type = fields.Selection([
        ('custom', 'Khoảng ngày'),
        ('month', 'Theo tháng'),
        ('quarter', 'Theo quý'),
        ('year', 'Theo năm'),
    ], string="Kỳ báo cáo", default='custom')

    month = fields.Selection([
        ('1', 'Tháng 1'), ('2', 'Tháng 2'), ('3', 'Tháng 3'),
        ('4', 'Tháng 4'), ('5', 'Tháng 5'), ('6', 'Tháng 6'),
        ('7', 'Tháng 7'), ('8', 'Tháng 8'), ('9', 'Tháng 9'),
        ('10', 'Tháng 10'), ('11', 'Tháng 11'), ('12', 'Tháng 12'),
    ], string="Tháng")

    quarter = fields.Selection([
        ('1', 'Quý 1'),
        ('2', 'Quý 2'),
        ('3', 'Quý 3'),
        ('4', 'Quý 4'),
    ], string="Quý")

    year = fields.Integer(
        string="Năm",
        default=lambda self: fields.Date.today().year,
    )

    @api.onchange('period_type', 'month', 'quarter', 'year')
    def _onchange_period_type(self):
        """
        Khi chọn Kỳ (Tháng / Quý / Năm) tự động set start_date / end_date.
        Nếu để 'Khoảng ngày' thì user tự nhập.
        """
        for wizard in self:
            today = fields.Date.context_today(wizard)
            y = wizard.year or today.year

            # Theo tháng
            if wizard.period_type == 'month' and wizard.month:
                m = int(wizard.month)
                start = pydate(y, m, 1)
                last_day = calendar.monthrange(y, m)[1]
                end = pydate(y, m, last_day)
                wizard.start_date = start
                wizard.end_date = end

            # Theo quý
            elif wizard.period_type == 'quarter' and wizard.quarter:
                q = int(wizard.quarter)
                start_month = 3 * (q - 1) + 1
                end_month = start_month + 2
                start = pydate(y, start_month, 1)
                last_day = calendar.monthrange(y, end_month)[1]
                end = pydate(y, end_month, last_day)
                wizard.start_date = start
                wizard.end_date = end

            # Theo năm
            elif wizard.period_type == 'year':
                wizard.start_date = pydate(y, 1, 1)
                wizard.end_date = pydate(y, 12, 31)

            # custom: không đụng tới start_date / end_date
            else:
                # không làm gì, cho user tự chọn ngày
                pass

    # --------- CÁC FIELD GỐC ----------
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
    )
    start_date = fields.Date(string="Ngày bắt đầu", help="Enter Start Date", required=True)
    end_date = fields.Date(string="Ngày kết thúc", help="Enter End Date", required=True)

    stock_location_id = fields.Many2one(
        'stock.location',
        required=True,
        domain=[('usage', '=', 'internal')],
    )

    state = fields.Selection([
        ('draft', 'New'),
        ('waiting', 'Waiting Another Move'),
        ('confirmed', 'Waiting Availability'),
        ('partially_available', 'Partially Available'),
        ('assigned', 'Available'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')
    ])
    @api.model
    def default_get(self, field_list):
        """Tự động fill lại wizard theo lần dùng gần nhất của user hiện tại."""
        res = super().default_get(field_list)

        # Tìm bản ghi wizard gần nhất của user này
        last_wizard = self.search(
            [('create_uid', '=', self.env.uid)],
            order='id desc',
            limit=1,
        )

        if last_wizard:
            # Các field muốn nhớ lại
            copy_fields = [
                'period_type',
                'year',
                'month',
                'quarter',
                'start_date',
                'end_date',
                'company_id',
                'stock_location_id',
            ]

            for fname in copy_fields:
                if fname in field_list:
                    field = self._fields.get(fname)
                    if not field:
                        continue
                    value = getattr(last_wizard, fname)
                    # Many2one -> gán id, còn lại gán thẳng
                    if isinstance(field, fields.Many2one):
                        res[fname] = value.id if value else False
                    else:
                        res[fname] = value

        else:
            # Không có lần trước -> để default như cũ của bạn
            # ví dụ: period_type = 'custom', start/end = hôm nay
            if 'period_type' in field_list and 'period_type' not in res:
                res['period_type'] = 'custom'
            # Có thể set thêm default ngày nếu thích
            # today = fields.Date.today()
            # if 'start_date' in field_list and 'start_date' not in res:
            #     res['start_date'] = today
            # if 'end_date' in field_list and 'end_date' not in res:
            #     res['end_date'] = today

        return res

    # --------- PDF ACTION ----------
    def pdf_action(self):
        """
        Generates the PDF report for the stock report wizard with the specified
        start and end date. Raises an error if the start date is later than the end date.
        """
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_("The start date must be earlier than the end date."))
        data = {
            'form_data': self.read()[0]
        }
        return self.env.ref('tk_stock_report.pdf_stock_report_action').report_action(self, data=data)

    def pdf_action_html(self):
        """
        Generates the PDF report for the stock report wizard with the specified
        start and end date. Raises an error if the start date is later than the end date.
        """
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_("The start date must be earlier than the end date."))
        data = {
            'form_data': self.read()[0]
        }
        return self.env.ref('tk_stock_report.pdf_stock_report_action_html').report_action(self, data=data)

    # --------- EXCEL ----------
    def btn_excel_action(self):
        """
        Triggers the generation of the Excel report for the stock report card.
        """
        return self.excel_stock_report_card()

    def excel_stock_report_card(self):
        """
        GIỮ NGUYÊN LOGIC CŨ CỦA BẠN, chỉ tận dụng start_date/end_date
        đã được tính theo kỳ ở trên.
        """
        self.ensure_one()
        if self.start_date > self.end_date:
            raise UserError(_("The start date must be earlier than the end date."))

        stock_move = self.env['stock.move'].search([
            ('create_date', '>=', self.start_date),
            ('create_date', '<=', self.end_date),
            ('company_id', '=', self.company_id.id),
            ('location_id', '=', self.stock_location_id.id),
            ('state', 'not in', ['draft', 'cancel']),
        ], order="date ASC")

        workbook = xlwt.Workbook(encoding="UTF-8")
        sheet1 = workbook.add_sheet('Stock-Report-Card', cell_overwrite_ok=True)

        # design format
        main_head = xlwt.easyxf('align: horiz center;borders: left thin, right thin, bottom thin;')
        font = xlwt.Font()
        font.bold = True
        font.height = 310
        main_head.font = font

        qty_format = xlwt.easyxf('font:bold True;align: horiz left;')
        qty_data_format = xlwt.easyxf('font:bold True;align: horiz left;')
        total_format = xlwt.easyxf('font:bold True;align: horiz left;')
        total_data_format = xlwt.easyxf('font:bold True;align: horiz left;')
        heading_text = xlwt.easyxf(
            'font:bold True;pattern: pattern solid, fore_colour gray25;align: horiz left;'
            'borders: top_color black, bottom_color black, right_color black,'
            'left_color black, top thin, bottom thin,right thin, left thin;'
        )
        heading_data = xlwt.easyxf('align: horiz left;font: height 200;')
        product_data = xlwt.easyxf(
            'font:bold True;align: horiz left;'
            'borders: top_color black, bottom_color black, right_color black,'
            'left_color black,left thin, top thin, bottom thin,right thin;'
        )
        normal_data = xlwt.easyxf('align: horiz left;')

        date_head = xlwt.XFStyle()
        date_head.num_format_str = 'dd/mm/yyyy'
        alignment = xlwt.Alignment()
        alignment.horz = xlwt.Alignment.HORZ_CENTER
        date_head.alignment = alignment
        borders = xlwt.Borders()
        borders.left = xlwt.Borders.THIN
        borders.right = xlwt.Borders.THIN
        borders.bottom = xlwt.Borders.THIN
        date_head.borders = borders

        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'dd/mm/yyyy'
        alignment2 = xlwt.Alignment()
        alignment2.horz = xlwt.Alignment.HORZ_LEFT
        date_format.alignment = alignment2

        # adjust row and columns
        sheet1.col(0).width = 5000
        sheet1.col(1).width = 5000
        sheet1.col(2).width = 5000
        sheet1.col(3).width = 5000
        sheet1.col(4).width = 5000
        sheet1.col(5).width = 5000

        # title
        sheet1.write(4, 0, 'Location', heading_text)
        sheet1.write(5, 0, 'Company', heading_text)
        sheet1.write(6, 0, 'Generated By', heading_text)

        # wizard company and location data
        sheet1.write_merge(4, 4, 1, 2, self.stock_location_id.complete_name, heading_data)
        sheet1.write_merge(5, 5, 1, 2, self.company_id.name, heading_data)
        sheet1.write_merge(6, 6, 1, 2, self.env.user.name, heading_data)

        # header
        sheet1.write_merge(0, 1, 1, 3, 'Stock Report', main_head)
        sheet1.write_merge(2, 2, 1, 3, f"{self.start_date} To {self.end_date}", date_head)

        # data header names
        headers = ["Date", "Origin", "In Qty", "Out Qty", "Balance"]
        column = 0
        for col in headers:
            sheet1.write(8, column, col, heading_text)
            column += 1

        # data info
        product_moves = {}

        for move in stock_move:
            product = f"[{move.product_id.default_code}] {move.product_id.name}"

            if product not in product_moves:
                product_moves[product] = {'balance': 0, 'moves': [], 'total_in': 0, 'total_out': 0}

            in_qty = 0
            out_qty = 0

            if move.picking_code == 'incoming':
                in_qty = move.product_qty
            elif move.picking_code == 'outgoing':
                out_qty = move.product_qty

            product_moves[product]['balance'] += in_qty - out_qty
            product_moves[product]['total_in'] += in_qty
            product_moves[product]['total_out'] += out_qty

            product_moves[product]['moves'].append({
                'date': move.date,
                'origin': move.origin or move.reference,
                'in_qty': in_qty,
                'out_qty': out_qty,
                'balance': product_moves[product]['balance']
            })

        # in products data moves
        row = 9

        for product, data in product_moves.items():
            sheet1.write_merge(row, row, 0, 4, product, product_data)
            row += 1
            sheet1.write_merge(row, row, 0, 3, 'Opening Quantity', qty_format)
            sheet1.write(row, 4, data['balance'], qty_data_format)
            row += 1

            for move in data['moves']:
                sheet1.write(row, 0, move['date'], date_format)
                sheet1.write(row, 1, move['origin'], normal_data)
                sheet1.write(row, 2, move['in_qty'], normal_data)
                sheet1.write(row, 3, move['out_qty'], normal_data)
                sheet1.write(row, 4, move['balance'], normal_data)
                row += 1

            sheet1.write_merge(row, row, 0, 1, 'TOTAL', total_format)
            sheet1.write(row, 2, data['total_in'], total_data_format)
            sheet1.write(row, 3, data['total_out'], total_data_format)
            sheet1.write(row, 4, data['balance'], total_data_format)
            row += 2

        stream = BytesIO()
        workbook.save(stream)
        filename = "Stock_Report_Card.xls"
        output = base64.encodebytes(stream.getvalue())
        attachment = self.env['ir.attachment'].sudo().create({
            'name': filename,
            'type': "binary",
            'public': False,
            'datas': output
        })
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self'
        }
