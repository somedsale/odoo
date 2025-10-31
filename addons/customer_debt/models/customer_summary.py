from odoo import models, fields, tools, api


class CustomerDebtSummary(models.Model):
    _name = "customer.debt.summary"
    _description = "Tổng hợp công nợ KH"
    _auto = False
    _rec_name = "partner_id"

    partner_id = fields.Many2one('res.partner', string="Khách hàng", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", readonly=True)

    project_ids = fields.Many2many(
        'project.project', string="Dự án", readonly=True,
        compute="_compute_projects", relation=None
    )
    contract_ids = fields.Many2many(
        'customer.contract', string="Hợp đồng", readonly=True,
        compute="_compute_contracts", relation=None
    )
    standalone_invoice_ids = fields.Many2many(
        'customer.invoice', string="Hóa đơn lẻ", readonly=True,
        compute="_compute_invoices", relation=None
    )

    project_ids_raw = fields.Char(readonly=True)
    contract_ids_raw = fields.Char(readonly=True)
    standalone_invoice_ids_raw = fields.Char(readonly=True)

    amount_total = fields.Monetary(string="Tổng giá trị HĐ", currency_field="currency_id", readonly=True)
    amount_invoiced = fields.Monetary(string="Đã xuất HĐ", currency_field="currency_id", readonly=True)
    amount_paid = fields.Monetary(string="Đã thu", compute="_compute_amount_paid", currency_field="currency_id", readonly=True)
    residual = fields.Monetary(
        string="Còn nợ",
        compute="_compute_residual",
        currency_field="currency_id",
        readonly=True
    )

    amount_final = fields.Monetary(string="Giá trị Quyết toán", currency_field="currency_id", readonly=True)
    warranty_amount = fields.Monetary(string="Giá trị Bảo hành", currency_field="currency_id", readonly=True)
    warranty_period = fields.Char(string="Thời gian bảo hành", readonly=True)
    note = fields.Text(string="Ghi chú", readonly=True)

    # 🔹 Công nợ cũ
    old_debt = fields.Monetary(
        string="Công nợ cũ",
        currency_field="currency_id",
        compute="_compute_old_debt",
        inverse="_inverse_old_debt",
        store=False,
        readonly=False,
        help="Số tiền còn nợ trước đây, sẽ cộng vào Còn nợ hiện tại."
    )

    # ==========================================================
    # =========== COMPUTE FUNCTIONS =============================
    # ==========================================================
    @api.depends("partner_id", "currency_id")
    def _compute_old_debt(self):
        for record in self:
            note_record = self.env['customer.summary.old.debt'].search([
                ('partner_id', '=', record.partner_id.id),
                ('currency_id', '=', record.currency_id.id)
            ], limit=1)
            record.old_debt = note_record.old_debt if note_record else 0.0

    def _inverse_old_debt(self):
        for record in self:
            note_record = self.env['customer.summary.old.debt'].search([
                ('partner_id', '=', record.partner_id.id),
                ('currency_id', '=', record.currency_id.id)
            ], limit=1)
            if note_record:
                note_record.old_debt = record.old_debt
            else:
                self.env['customer.summary.old.debt'].create({
                    'partner_id': record.partner_id.id,
                    'currency_id': record.currency_id.id,
                    'old_debt': record.old_debt
                })

    @api.depends("contract_ids.amount_receipt")
    def _compute_amount_paid(self):
        for record in self:
            record.amount_paid = sum(record.contract_ids.mapped("amount_receipt"))

    @api.depends("amount_invoiced", "old_debt", "amount_paid")
    def _compute_residual(self):
        """Còn nợ = Tổng đã xuất HĐ - Đã thu + Công nợ cũ"""
        for record in self:
            record.residual = (record.amount_invoiced or 0.0) - (record.amount_paid or 0.0) + (record.old_debt or 0.0)

    @api.depends('standalone_invoice_ids_raw')
    def _compute_invoices(self):
        for rec in self:
            ids = [int(x) for x in (rec.standalone_invoice_ids_raw or '').split(',') if x]
            rec.standalone_invoice_ids = [(6, 0, ids)]

    @api.depends('project_ids_raw')
    def _compute_projects(self):
        for rec in self:
            ids = [int(x) for x in (rec.project_ids_raw or '').split(',') if x]
            rec.project_ids = [(6, 0, ids)]

    @api.depends('contract_ids_raw')
    def _compute_contracts(self):
        for rec in self:
            ids = [int(x) for x in (rec.contract_ids_raw or '').split(',') if x]
            rec.contract_ids = [(6, 0, ids)]

    # ==========================================================
    # =========== SQL VIEW =====================================
    # ==========================================================
    def init(self):
        # 🔹 Xóa object cũ (có thể là table hoặc view)
        self._cr.execute("""
            DO $$
            BEGIN
                -- Nếu là VIEW thì xóa view
                IF EXISTS (
                    SELECT 1 FROM pg_views WHERE viewname = 'customer_debt_summary'
                ) THEN
                    EXECUTE 'DROP VIEW IF EXISTS customer_debt_summary CASCADE';
                -- Nếu là TABLE thì xóa table
                ELSIF EXISTS (
                    SELECT 1 FROM pg_tables WHERE tablename = 'customer_debt_summary'
                ) THEN
                    EXECUTE 'DROP TABLE IF EXISTS customer_debt_summary CASCADE';
                END IF;
            END$$;
        """)

        # 🔹 Tạo lại view
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                WITH
                invoice_sum AS (
                    SELECT contract_id, SUM(amount_total) AS amount_invoiced
                    FROM customer_invoice
                    GROUP BY contract_id
                ),
                standalone_invoices AS (
                    SELECT partner_id, STRING_AGG(id::text, ',') AS invoice_ids_raw
                    FROM customer_invoice
                    WHERE contract_id IS NULL
                    GROUP BY partner_id
                )
                SELECT
                    row_number() OVER () AS id,  -- ✅ tạo id duy nhất cho mỗi record
                    c.partner_id,
                    STRING_AGG(DISTINCT c.project_id::text, ',') AS project_ids_raw,
                    STRING_AGG(DISTINCT c.id::text, ',') AS contract_ids_raw,
                    s.invoice_ids_raw AS standalone_invoice_ids_raw,
                    c.currency_id,
                    COALESCE(SUM(c.amount_total), 0) AS amount_total,
                    COALESCE(SUM(inv.amount_invoiced), 0) AS amount_invoiced,
                    0.0::numeric AS amount_paid,
                    0.0::numeric AS residual,  -- residual tính lại bằng compute
                    0.0::numeric AS amount_final,
                    0.0::numeric AS warranty_amount,
                    NULL::varchar AS warranty_period,
                    NULL::text AS note
                FROM customer_contract c
                LEFT JOIN invoice_sum inv ON inv.contract_id = c.id
                LEFT JOIN standalone_invoices s ON s.partner_id = c.partner_id
                GROUP BY c.partner_id, c.currency_id, s.invoice_ids_raw
            )
        """)



# ==========================================================
# =========== MODEL LƯU CÔNG NỢ CŨ =========================
# ==========================================================
class CustomerSummaryOldDebt(models.Model):
    _name = "customer.summary.old.debt"
    _description = "Công nợ cũ của khách hàng"
    _rec_name = "partner_id"

    partner_id = fields.Many2one("res.partner", string="Khách hàng", required=True, ondelete="cascade")
    currency_id = fields.Many2one("res.currency", string="Tiền tệ", required=True, default=lambda self: self.env.company.currency_id)
    old_debt = fields.Monetary(string="Công nợ cũ", currency_field="currency_id")
    note = fields.Text("Ghi chú")
    interpretation = fields.Char("Diễn giải")

    _sql_constraints = [
        ("partner_currency_unique",
         "unique(partner_id, currency_id)",
         "Mỗi khách hàng và tiền tệ chỉ có một bản ghi công nợ cũ."),
    ]
