from odoo import fields, models


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    move_line_image = fields.Binary(
        string="Hình ảnh",
        related="product_id.image_1920",
        help="Hình ảnh sản phẩm trên dòng chứng từ kho",
    )
    scheduled_date = fields.Datetime(
        related="picking_id.scheduled_date",
        string='Ngày đã lên lịch',
        store=True,
        help="Ngày đã lên lịch của phiếu dịch chuyển",
    )
    date_done = fields.Datetime(
        related="picking_id.date_done",
        string='Ngày hoàn tất',
        help="Ngày hoàn tất của phiếu dịch chuyển",
    )
    code = fields.Selection(
        related="picking_id.picking_type_id.code",
        help="Mã loại hoạt động kho",
    )
    picking_type_id = fields.Many2one(
        related="picking_id.picking_type_id",
        store=True,
        help="Loại hoạt động kho",
    )
    origin = fields.Char(
        related="picking_id.origin",
        store=True,
        help="Chứng từ gốc của hoạt động kho",
    )
    reserved_available = fields.Float(
        related="picking_id.move_ids.forecast_availability",
        help="Số lượng đã được dành sẵn",
    )
    date_deadline = fields.Datetime(
        related="picking_id.date_deadline",
        string="Hạn chót",
        help="Hạn chót thực hiện phiếu dịch chuyển",
    )
    has_deadline_issue = fields.Boolean(
        string="Bị trễ hạn",
        related="picking_id.has_deadline_issue",
        help="Đánh dấu nếu phiếu dịch chuyển bị trễ so với hạn chót",
    )