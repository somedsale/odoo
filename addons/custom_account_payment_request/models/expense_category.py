from odoo import models, fields, api
from odoo.exceptions import ValidationError
import unicodedata
import re


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
        ('fixed_cost', 'Chi phí cố định'),
        ('irregular_expenses', 'Chi phí không thường xuyên'),
        ('estimated_cost', 'Chi phí dự kiến theo dự án'),
    ], required=True, index=True,string="Phân loại")

    parent_id = fields.Many2one('expense.category', string="Khoản mục", index=True)
    parent_path = fields.Char(index=True)
    active = fields.Boolean(default=True)
    code_ref = fields.Char("Mã tham chiếu", readonly=True)

    # ============================================================
    # NORMALIZE TEXT
    # ============================================================
    @staticmethod
    def _normalize(text):
        text = unicodedata.normalize('NFD', text)
        return ''.join(c for c in text if unicodedata.category(c) != 'Mn')

    # ============================================================
    # HÀM TẠO BASE CODE TỪ TÊN (KHÔNG CHỨA SỐ)
    # ============================================================
    def _build_base_code(self, name):
        name = (name or "").strip()

        # bỏ phần trong ngoặc
        name = name.split('(')[0].strip()

        # bỏ dấu tiếng Việt
        clean = self._normalize(name.replace('+', ' '))
        parts = clean.split()

        if not parts:
            return False

        # Nếu chỉ 1 từ → dùng nguyên từ
        if len(parts) == 1:
            return parts[0].upper()

        # Nếu nhiều từ → ghép ký tự đầu + giữ nguyên phần có số
        code = parts[0][0].upper()
        for p in parts[1:]:
            if re.search(r'\d+', p):
                code += p.upper()
            else:
                code += p[0].upper()
        return code

    # ============================================================
    # TẠO CODE_REF CHO 1 RECORD – xử lý trùng tại chỗ
    # ============================================================
    def _generate_unique_code(self, base_code):
        if not base_code:
            return False

        # tìm tất cả code trùng prefix
        existing = self.search([
            ('code_ref', 'like', f"{base_code}%"),
            ('id', '!=', self.id),
        ]).mapped('code_ref')

        # chưa có ai dùng → dùng luôn
        if base_code not in existing:
            return base_code

        # tìm số đuôi cao nhất
        max_num = 0
        pattern = re.compile(r'^' + re.escape(base_code) + r'(\d+)$')

        for code in existing:
            m = pattern.match(code)
            if m:
                max_num = max(max_num, int(m.group(1)))

        return f"{base_code}{max_num + 1}"

    # ============================================================
    # CREATE → tự động sinh code_ref
    # ============================================================
    @api.model
    def create(self, vals):
        rec = super().create(vals)

        if not rec.code_ref:
            base = rec._build_base_code(rec.name)
            rec.code_ref = rec._generate_unique_code(base)

        return rec
    def write(self, vals):
        res = super().write(vals)

        for rec in self:
            if 'name' in vals or 'parent_id' in vals:
                base = rec._build_base_code(rec.name)
                rec.code_ref = rec._generate_unique_code(base)

        return res

    # ============================================================
    # INIT → chạy 1 lần sau khi upgrade module
    # ============================================================
    @api.model
    def init(self):
        records = self.search([])

        for rec in records:
            base = rec._build_base_code(rec.name)
            new_code = rec._generate_unique_code(base)
            rec.write({'code_ref': new_code})

    # ============================================================
    # CONSTRAINT
    # ============================================================
    _sql_constraints = [
        ('name_class_uniq', 'unique(name, classification, parent_id)',
         'Khoản mục đã tồn tại trong cùng phân loại/cha.')
    ]

    @api.constrains('parent_id')
    def _check_parent_classification(self):
        for rec in self:
            if rec.parent_id and rec.parent_id.classification != rec.classification:
                raise ValidationError("Phân loại của khoản mục con phải trùng với khoản mục cha.")
