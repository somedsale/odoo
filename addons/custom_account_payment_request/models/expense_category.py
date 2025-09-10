from odoo import models, fields, api
from odoo.exceptions import ValidationError

class ExpenseCategory(models.Model):
    _name = "expense.category"
    _description = "Khoản mục chi phí"
    _parent_store = True
    _order = "parent_path, name"

    name = fields.Char("Tên khoản mục", required=True)
    classification = fields.Selection([
        ('employee', 'Khoản vay nội bộ (nhân viên)'),
        ('office', 'Chi phí tại công ty'),
        ('project', 'Chi phí các công trình'),
        ('estimated_cost', 'Chi phí dự kiến theo dự án'),
    ], string="Phân loại", required=True, index=True)

    parent_id = fields.Many2one('expense.category', string="Khoản mục", index=True)
    # child_ids = fields.One2many('expense.category', 'parent_id', string="Khoản mục con")
    parent_path = fields.Char(index=True)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('name_class_uniq', 'unique(name, classification, parent_id)',
         'Khoản mục đã tồn tại trong cùng phân loại/cha.')
    ]

    @api.constrains('parent_id')
    def _check_parent_classification(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.classification != rec.classification:
                raise ValidationError("Phân loại của khoản mục con phải trùng với khoản mục cha.")
