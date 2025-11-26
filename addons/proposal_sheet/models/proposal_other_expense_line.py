from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ProposalOtherExpenseLine(models.Model):
    _name = 'proposal.other.expense.line'
    _description = 'Chi phí ngoài công trình'
    _inherit = ['mail.thread']

    _order = "sequence, id"
    active = fields.Boolean(string='Active', default=True)

    # Link ngược về proposal.sheet
    sheet_id = fields.Many2one(
        'proposal.sheet',
        string='Phiếu Đề Xuất',
        required=True,
        ondelete='cascade',
    )
    unit=fields.Many2one('uom.uom', string='Đơn vị tính')
    price_unit=fields.Float(string='Đơn giá', digits=(16, 4))
    quantity =fields.Float(string='Số lượng', default=1.0, digits=(16, 1))

    # Nội dung chi / thông tin chính
    content = fields.Char(string='Nội dung chi', required=True, tracking=True)
    amount = fields.Float(string='Số tiền', required=True, tracking=True,compute ='_compute_amount', store=True)
    date = fields.Date(string='Ngày dự chi', default=fields.Date.today, tracking=True)
    object = fields.Many2one('res.partner', string='Đối tượng/NCC')
    note = fields.Text(string='Ghi chú')
    type = fields.Selection([('other', 'Khác')], default='other', required=True, readonly=True)
    cost_classification = fields.Selection([
        ('employee', 'Khoản vay nội bộ (nhân viên)'),
        ('office', 'Chi phí tại công ty'),
        ('project', 'Chi phí các công trình'),
        ('fixed_cost', 'Chi phí cố định'),
        ('irregular_expenses', 'Chi phí không thường xuyên'),
        ('estimated_cost', 'Chi phí dự kiến theo dự án'),
    ], string="Phân loại", required=True, index=True)
    currency_id = fields.Many2one(
        'res.currency',
        string='Tiền tệ',
        default=lambda self: self.env.company.currency_id.id,
    )

    sequence = fields.Integer(string="", default=10)

    # ========== CONSTRAINTS & LOGIC ==========
    @api.depends('price_unit','quantity')
    def _compute_amount(self):
        for line in self:
            line.amount = line.price_unit * line.quantity

    @api.constrains('amount')
    def _check_amount(self):
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Số tiền phải lớn hơn 0."))

    @api.model
    def create(self, vals):
        _logger.info("Creating ProposalOtherExpenseLine with vals: %s", vals)

        # Bắt buộc sheet tồn tại & loại phiếu phù hợp
        if vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError(_("Phiếu đề xuất không tồn tại."))
            if sheet.type != 'other':
                raise ValidationError(_("Chỉ được thêm dòng 'Chi phí ngoài công trình' vào phiếu loại 'Khác'."))
        else:
            raise ValidationError(_("Thiếu thông tin Phiếu đề xuất (sheet_id)."))

        return super().create(vals)

    def write(self, vals):
        _logger.info("Writing ProposalOtherExpenseLine with vals: %s", vals)

        if 'sheet_id' in vals and vals.get('sheet_id'):
            sheet = self.env['proposal.sheet'].browse(vals['sheet_id'])
            if not sheet.exists():
                raise ValidationError(_("Phiếu đề xuất không tồn tại."))
            if sheet.type != 'other':
                raise ValidationError(_("Chỉ được thêm dòng 'Chi phí ngoài công trình' vào phiếu loại 'Khác'."))

        res = super().write(vals)

        # Kiểm tra lại amount sau khi ghi
        for line in self:
            if line.amount <= 0:
                raise ValidationError(_("Số tiền phải lớn hơn 0."))

        return res

    # Archive / Unarchive giống ProposalExpenseLine
    def archive(self):
        self.write({'active': False})
        self.message_post(body=_('Dòng chi phí ngoài công trình đã được lưu trữ.'))

    def unarchive(self):
        self.write({'active': True})
        self.message_post(body=_('Dòng chi phí ngoài công trình đã được khôi phục.'))
