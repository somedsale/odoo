# file: your_module/controllers/dashboard.py
from odoo import http
from odoo.http import request

class AccountingDashboardController(http.Controller):
    
    @http.route('/accounting/dashboard/data', type='json', auth='user')
    def get_dashboard_data(self):
        # ví dụ đếm đơn hàng, doanh thu, v.v...
        quotations = request.env['sale.order'].sudo().search_count([])
        orders = request.env['sale.order'].sudo().search_count([('state','=','sale')])
        revenues = sum(request.env['account.move'].sudo().search([('state','=','posted')]).mapped('amount_total'))
        avg_order = revenues / orders if orders else 0

        return {
            "quotations": quotations,
            "orders": orders,
            "revenues": revenues,
            "avg_order": avg_order,
        }
