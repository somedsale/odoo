from odoo import models, fields, tools, api

class CustomerDebtSummary(models.Model):
    _name = "customer.debt.summary"
    _description = "Tổng hợp công nợ KH"
    _auto = False

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

    # Raw ID fields
    project_ids_raw = fields.Char(readonly=True)
    contract_ids_raw = fields.Char(readonly=True)
    standalone_invoice_ids_raw = fields.Char(readonly=True)

    # ======= Các field giá trị =======
    amount_total = fields.Monetary(string="Tổng giá trị HĐ", currency_field="currency_id", readonly=True)
    amount_invoiced = fields.Monetary(string="Đã xuất HĐ", currency_field="currency_id", readonly=True)
    amount_paid = fields.Monetary(string="Đã thu", compute="_compute_amount_paid", currency_field="currency_id", readonly=True)
    residual = fields.Monetary(string="Còn nợ", currency_field="currency_id", readonly=True)

    # ======= Các field ảo thêm để render report =======
    amount_final = fields.Monetary(string="Giá trị Quyết toán", currency_field="currency_id", readonly=True)
    warranty_amount = fields.Monetary(string="Giá trị Bảo hành", currency_field="currency_id", readonly=True)
    warranty_period = fields.Char(string="Thời gian bảo hành", readonly=True)
    note = fields.Text(string="Ghi chú", readonly=True)


    @api.depends("contract_ids.amount_receipt")
    def _compute_amount_paid(self):
        for record in self:
            record.amount_paid = sum(record.contract_ids.mapped("amount_receipt"))
    # ===== COMPUTE FIELDS =====
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

    # ===== SQL VIEW =====
    def init(self):
        tools.drop_view_if_exists(self._cr, self._table)
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
                    MIN(c.id) AS id,
                    c.partner_id,
                    STRING_AGG(DISTINCT c.project_id::text, ',') AS project_ids_raw,
                    STRING_AGG(DISTINCT c.id::text, ',') AS contract_ids_raw,
                    s.invoice_ids_raw AS standalone_invoice_ids_raw,
                    c.currency_id,
                    COALESCE(SUM(c.amount_total), 0) AS amount_total,
                    COALESCE(SUM(inv.amount_invoiced), 0) AS amount_invoiced,

                    /* 🔹 Vì bỏ phiếu thu nên đặt mặc định 0 */
                    0.0::numeric AS amount_paid,
                    (COALESCE(SUM(inv.amount_invoiced), 0)) AS residual,

                    /* 🔹 Bổ sung các cột ảo để tránh lỗi template */
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
