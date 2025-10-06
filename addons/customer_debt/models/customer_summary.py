from odoo import models, fields, tools,api

class CustomerDebtSummary(models.Model):
    _name = "customer.debt.summary"
    _description = "Tổng hợp công nợ KH"
    _auto = False

    partner_id = fields.Many2one('res.partner', string="Khách hàng", readonly=True)
    project_id = fields.Many2one('project.project', string="Dự án", readonly=True)
    contract_id = fields.Many2one('customer.contract', string="Hợp đồng", readonly=True)
    currency_id = fields.Many2one('res.currency', string="Tiền tệ", readonly=True)

    amount_total = fields.Monetary(string="Tổng giá trị HĐ", currency_field="currency_id", readonly=True)
    amount_invoiced = fields.Monetary(string="Đã xuất HĐ", currency_field="currency_id", readonly=True)
    amount_paid = fields.Monetary(string="Đã thanh toán", currency_field="currency_id", readonly=True)
    residual = fields.Monetary(string="Còn nợ", currency_field="currency_id", readonly=True)

    def init(self):
        # Xóa table hoặc view cũ nếu tồn tại
        self._cr.execute("""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_views WHERE viewname = 'customer_debt_summary') THEN
                    EXECUTE 'DROP VIEW IF EXISTS customer_debt_summary CASCADE';
                ELSIF EXISTS (SELECT 1 FROM pg_tables WHERE tablename = 'customer_debt_summary') THEN
                    EXECUTE 'DROP TABLE IF EXISTS customer_debt_summary CASCADE';
                END IF;
            END$$;
        """)

        # Tạo lại view tổng hợp công nợ
        tools.drop_view_if_exists(self._cr, self._table)
        self._cr.execute(f"""
            CREATE OR REPLACE VIEW {self._table} AS (
                SELECT
                    MIN(c.id) AS id,
                    c.partner_id,
                    c.project_id,
                    c.id AS contract_id,
                    c.currency_id,

                    -- Tổng giá trị hợp đồng (lấy từ chính contract)
                    COALESCE(c.amount_total, 0) AS amount_total,

                    -- Tổng hóa đơn đã xuất của hợp đồng
                    COALESCE(SUM(inv.amount_total), 0) AS amount_invoiced,

                    -- Giả sử chưa có bảng thanh toán, gán 0 tạm
                    0 AS amount_paid,

                    -- Còn nợ = tổng HĐ - đã thanh toán
                    COALESCE(SUM(inv.amount_total), 0) AS residual

                FROM customer_contract c
                LEFT JOIN customer_invoice inv ON inv.contract_id = c.id
                GROUP BY 
                    c.id,
                    c.partner_id,
                    c.project_id,
                    c.currency_id,
                    c.amount_total
            )
        """)
    @api.model
    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        """
        Tùy chỉnh hiển thị dòng group để:
        - Tổng hợp theo khách hàng
        - Giữ chi tiết từng hợp đồng ở cấp dưới
        """
        results = super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

        # Khi group theo partner_id
        if groupby and groupby[0] == 'partner_id':
            for rec in results:
                partner_id = rec.get('partner_id') and rec['partner_id'][0]
                if partner_id:
                    # Lấy tất cả hợp đồng của KH này
                    contracts = self.env['customer.debt.summary'].search([('partner_id', '=', partner_id)])
                    rec['amount_total'] = sum(contracts.mapped('amount_total'))
                    rec['amount_invoiced'] = sum(contracts.mapped('amount_invoiced'))
                    rec['amount_paid'] = sum(contracts.mapped('amount_paid'))
                    rec['residual'] = sum(contracts.mapped('residual'))

        return results
