from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AccountPaymentRequestLine(models.Model):
    _name = 'account.payment.request.line'
    _description = 'Chi tiết phiếu chi theo phiếu đề xuất'
    _order = 'id'


    payment_request_id = fields.Many2one(
        'account.payment.request',
        string='Phiếu chi',
        required=True,
        ondelete='cascade'
    )

    line_type = fields.Selection([
        ('proposal', 'Theo phiếu đề xuất'),
        ('manual', 'Chi thủ công'),
    ], string='Loại dòng', default='proposal', required=True)

    proposal_sheet_id = fields.Many2one(
        'proposal.sheet',
        string='Phiếu đề xuất'
    )

    project_id = fields.Many2one(
        'project.project',
        string='Dự án',
        related='proposal_sheet_id.project_id',
        store=True,
        readonly=True
    )

    requested_by = fields.Many2one(
        'res.users',
        string='Người đề xuất',
        related='proposal_sheet_id.requested_by',
        store=True,
        readonly=True
    )

    proposal_date = fields.Date(
        string='Ngày đề xuất',
        related='proposal_sheet_id.date_proposal',
        store=True,
        readonly=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        related='payment_request_id.currency_id',
        store=True,
        readonly=True
    )

    amount = fields.Float(string='Số tiền chi', required=True, default=0.0)
    interpretation = fields.Char(string='Diễn giải')
    note = fields.Text(string='Ghi chú')
    payment_create_date = fields.Datetime(
        string='Ngày tạo chi',
        related='payment_request_id.create_date',
        store=True,
        readonly=True
    )

    payment_date = fields.Date(
        string='Ngày chi',
        related='payment_request_id.date_payment',
        store=True,
        readonly=True
    )

    payment_state = fields.Selection(
        related='payment_request_id.state',
        string='Trạng thái',
        store=True,
        readonly=True
    )

    payment_name = fields.Char(
        string='Phiếu chi',
        related='payment_request_id.name',
        store=True,
        readonly=True
    )

    manual_name = fields.Char(string='Tên khoản chi tay')

    display_name_line = fields.Char(
        string='Diễn giải hiển thị',
        compute='_compute_display_name_line',
        store=True
    )

    @api.depends('line_type', 'proposal_sheet_id', 'manual_name', 'interpretation')
    def _compute_display_name_line(self):
        for rec in self:
            if rec.line_type == 'proposal' and rec.proposal_sheet_id:
                rec.display_name_line = rec.proposal_sheet_id.name
            else:
                rec.display_name_line = rec.manual_name or rec.interpretation or 'Chi thủ công'

    @api.onchange('line_type')
    def _onchange_line_type(self):
        for rec in self:
            if rec.line_type == 'manual':
                rec.proposal_sheet_id = False
            elif rec.line_type == 'proposal' and not rec.manual_name:
                rec.manual_name = False

    @api.constrains('amount')
    def _check_amount(self):
        for rec in self:
            if rec.amount < 0:
                raise ValidationError("Số tiền chi trên từng dòng không được âm.")

    @api.constrains('line_type', 'proposal_sheet_id', 'manual_name')
    def _check_required_fields(self):
        for rec in self:
            if rec.line_type == 'proposal' and not rec.proposal_sheet_id:
                raise ValidationError("Dòng 'Theo phiếu đề xuất' bắt buộc phải chọn phiếu đề xuất.")
            if rec.line_type == 'manual' and not (rec.manual_name or rec.interpretation):
                raise ValidationError("Dòng chi thủ công phải nhập tên khoản chi hoặc diễn giải.")

    @api.constrains('proposal_sheet_id', 'payment_request_id')
    def _check_unique_proposal_in_payment(self):
        for rec in self:
            if not rec.payment_request_id or not rec.proposal_sheet_id:
                continue
            dup = self.search_count([
                ('id', '!=', rec.id),
                ('payment_request_id', '=', rec.payment_request_id.id),
                ('proposal_sheet_id', '=', rec.proposal_sheet_id.id),
            ])
            if dup:
                raise ValidationError("Một phiếu đề xuất chỉ nên xuất hiện 1 lần trong cùng 1 phiếu chi.")