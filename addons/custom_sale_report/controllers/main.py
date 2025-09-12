from odoo import http
from odoo.http import request

class CustomSaleReportController(http.Controller):

    @http.route(['/custom_sale_report/render/<int:report_id>'], type='http', auth="user")
    def render_report(self, report_id):
        record = request.env['custom.sale.report'].sudo().browse(report_id)
        if not record.exists():
            return request.not_found()
        values = record.get_report_data()
        return request.render("custom_sale_report.report_custom_sale", {'doc': values})
