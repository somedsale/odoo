from odoo import models, fields, api
from datetime import datetime, date
def _as_date(v):
    """Trả về kiểu datetime.date cho mọi giá trị ngày/ngày-giờ."""
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    # Trường hợp string (hiếm khi), cố parse qua fields.Date
    try:
        return fields.Date.from_string(v)
    except Exception:
        return None
class SupplierContract(models.Model):
    _name = "supplier.contract"
    _description = "Supplier Contract"

    name = fields.Char("Mã")
    partner_id = fields.Many2one("res.partner", string="Nhà cung cấp", required=True, domain=[("supplier_rank", ">", 0)])
    project_id = fields.Many2one("project.project", string="Dự án", required=True)
    interpretation = fields.Char("Diễn giải")
    contract_date = fields.Date("Ngày Hợp đồng")
    amount = fields.Monetary("Giá trị Hợp đồng", currency_field="currency_id")
    currency_id = fields.Many2one("res.currency", default=lambda self: self.env.company.currency_id)
    due_date = fields.Date("Ngày đến hạn",compute="_compute_due_date", store=True)
    create_date = fields.Datetime("Ngày tạo", default=fields.Datetime.now)
    total_invoices = fields.Monetary("Tổng giá trị hóa đơn", compute="_compute_total_invoices", store=True, currency_field="currency_id")
    total_settlements = fields.Monetary("Tổng giá trị hồ sơ quyết toán", compute="_compute_total_settlements", store=True, currency_field="currency_id")
    paid_amount = fields.Monetary("Tổng giá trị đã thanh toán", compute="_compute_paid_amount", store=True, currency_field="currency_id")
    residual_amount = fields.Monetary("Còn nợ", compute="_compute_residual", store=True, currency_field="currency_id")
    advance_amount = fields.Monetary("Số tiền đã tạm ứng/ chưa hóa đơn", compute="_compute_advance_amount", store=True, currency_field="currency_id")
    account_payment_request_ids = fields.One2many(
        "account.payment.request", 
        "supplier_contract_id", 
        string="Phiếu chi"
    )
    settlement_ids = fields.One2many("supplier.settlement", "contract_id", string="Hồ sơ quyết toán")
    invoice_ids = fields.One2many("supplier.invoice", "contract_id", string="Hóa đơn")
    number_contract = fields.Char("Số hợp đồng", store=True)
    @api.depends("invoice_ids.due_date", "invoice_ids.amount", "account_payment_request_ids.total", "advance_amount")
    def _compute_due_date(self):
        for record in self:
            dates = []
            if record.advance_amount > 0:
                record.due_date = False
            else:
                for invoice in record.invoice_ids:
                    payments = record.account_payment_request_ids.filtered(lambda r: r.invoice_id == invoice)
                    total = sum(p.total for p in payments)
                    temp = invoice.amount - total
                    if temp > 0:
                        if invoice.due_date:
                            dates.append(invoice.due_date)
                if dates:  
                    record.due_date = min(dates)
                else:
                    record.due_date = False
            
    @api.depends("invoice_ids.amount")
    def _compute_total_invoices(self):
        for record in self:
            record.total_invoices = sum(record.invoice_ids.mapped("amount"))
    @api.depends("settlement_ids.amount")
    def _compute_total_settlements(self):
        for record in self:
            record.total_settlements = sum(record.settlement_ids.mapped("amount"))
    @api.depends("account_payment_request_ids.total", "account_payment_request_ids.state")
    def _compute_paid_amount(self):
        for record in self:
            record.paid_amount = sum(request.total for request in record.account_payment_request_ids if request.state == 'done')
    @api.depends("amount", "paid_amount", "advance_amount", "account_payment_request_ids.total", "account_payment_request_ids.state", "invoice_ids.amount")
    def _compute_residual(self):
        for record in self:
            residual_amount = record.total_invoices - record.paid_amount
            if residual_amount < 0:
                residual_amount = residual_amount
            record.residual_amount = residual_amount
    @api.depends("total_invoices", "paid_amount")
    def _compute_advance_amount(self):
        for record in self:
            advance_amount = record.paid_amount - record.total_invoices
            if advance_amount < 0:
                advance_amount = 0
            record.advance_amount = advance_amount
    @api.onchange("residual_amount")
    def _onchange_residual_amount(self):
        for record in self:
            if record.residual_amount == 0:
                record.due_date = False
    def action_open_invoices(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hóa đơn NCC",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_project_id": self.project_id.id,
            },
        }

    # Phiếu chi thuộc HĐ này (hoặc hóa đơn của HĐ này)
    def action_open_payment_requests(self):
        self.ensure_one()
        # nếu model account.payment.request có field invoice_id + supplier_contract_id như bạn dùng
        return {
            "type": "ir.actions.act_window",
            "name": "Phiếu chi",
            "res_model": "account.payment.request",
            "view_mode": "tree,form",
            "target": "current",
            "domain": ["|", ("supplier_contract_id", "=", self.id),
                             ("invoice_id.contract_id", "=", self.id)],
            "context": {
                "default_supplier_contract_id": self.id,
                "default_partner_id": self.partner_id.id,
                "default_project_id": self.project_id.id,
            },
        }

    # Hồ sơ quyết toán thuộc HĐ này
    def action_open_settlements(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Hồ sơ quyết toán",
            "res_model": "supplier.settlement",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
            },
        }

    # “Còn nợ”: mở danh sách hóa đơn chưa thanh toán (tùy bạn muốn mở invoices hay payment requests)
    def action_open_residual(self):
        self.ensure_one()
        # ví dụ mở hóa đơn của HĐ này (bạn có thể thêm điều kiện due_date/quá hạn tùy ý)
        return {
            "type": "ir.actions.act_window",
            "name": "Công nợ chưa thanh toán",
            "res_model": "supplier.invoice",
            "view_mode": "tree,form",
            "target": "current",
            "domain": [("contract_id", "=", self.id)],
            "context": {
                "default_contract_id": self.id,
                "search_default_contract_id": 1,
            },
        }

    def get_report_rows(self):
        """
        rows: list các dict cho QWeb, mỗi dict gồm:
          - 'invoice': record hoặc None
          - 'payment': record hoặc None
          - 'running_balance': số dư còn lại SAU DÒNG NÀY
          - 'is_first_invoice_row': True nếu là dòng đầu tiên của một hóa đơn
        """
        self.ensure_one()
        rows = []

        # ===== 1) Sắp xếp HÓA ĐƠN: theo ngày -> số =====
        # Chuẩn hoá ngày: inv.date (Date), inv.create_date (Datetime) -> date
        invoices = self.invoice_ids.sorted(
            key=lambda inv: (
                _as_date(inv.date)                                   # có thể là Date
                or (_as_date(inv.create_date)                        # create_date (Datetime) -> date
                    or fields.Date.today()),                         # fallback an toàn
                inv.name or ''
            )
        )

        # ===== 2) Sắp xếp THANH TOÁN =====
        # Ưu tiên ngày của hoá đơn gắn kèm (nếu có) -> ngày thanh toán -> id
        def _payment_sort_key(p):
            inv_date = None
            if getattr(p, 'invoice_id', False) and p.invoice_id:
                inv_date = _as_date(getattr(p.invoice_id, 'date', None)) \
                           or _as_date(getattr(p.invoice_id, 'create_date', None))

            pay_primary = inv_date or _as_date(p.date_payment) \
                          or _as_date(p.create_date) \
                          or fields.Date.today()

            pay_secondary = _as_date(p.date_payment) \
                            or _as_date(p.create_date) \
                            or fields.Date.today()

            return (pay_primary, pay_secondary, p.id or 0)

        payments = self.account_payment_request_ids.sorted(key=_payment_sort_key)

        # ===== 3) Gom theo invoice_id (False = không gắn hoá đơn) =====
        by_inv = {}
        for p in payments:
            key = p.invoice_id.id if getattr(p, 'invoice_id', False) else False
            by_inv.setdefault(key, []).append(p)

        # ===== 4) Cho từng hoá đơn: tính running balance của HOÁ ĐƠN =====
        for inv in invoices:
            plist = by_inv.pop(inv.id, [])
            # Thứ tự lũy kế theo ngày trả + id (đã dùng _payment_sort_key, nhưng giữ rõ ràng ở đây)
            plist = sorted(plist, key=lambda p: (
                _as_date(p.date_payment) or _as_date(p.create_date) or fields.Date.today(),
                p.id or 0
            ))

            running = float(inv.amount or 0.0)  # bắt đầu từ số tiền hóa đơn
            if plist:
                for idx, p in enumerate(plist):
                    running -= float(p.total or 0.0)   # cho phép âm (trả dư)
                    rows.append({
                        'invoice': inv,
                        'payment': p,
                        'running_balance': running,   # còn lại sau dòng này
                        'is_first_invoice_row': (idx == 0),
                    })
            else:
                # Không có payment: 1 dòng, còn nợ = toàn bộ tiền hóa đơn
                rows.append({
                    'invoice': inv,
                    'payment': None,
                    'running_balance': float(inv.amount or 0.0),
                    'is_first_invoice_row': True,
                })

        # ===== 5) Thanh toán KHÔNG gắn hoá đơn: lũy kế âm (tạm ứng) =====
        unlinked = by_inv.get(False, [])
        unlinked = sorted(unlinked, key=lambda p: (
            _as_date(p.date_payment) or _as_date(p.create_date) or fields.Date.today(),
            p.id or 0
        ))
        advance_running = 0.0  # lũy kế âm
        for p in unlinked:
            advance_running -= float(p.total or 0.0)  # tăng âm
            rows.append({
                'invoice': None,                 # phần hóa đơn trống
                'payment': p,
                'running_balance': advance_running,  # số dư tạm ứng (âm)
                'is_first_invoice_row': False,
            })

        return rows
class ResPartner(models.Model):
    _inherit = "res.partner"

    contract_ids = fields.One2many("supplier.contract", "partner_id", string="Hợp đồng nhà cung cấp")