from odoo import api, models

class InventoryPDFReport(models.AbstractModel):
    _name = 'report.inventory_report_generator.inventory_pdf_report'

    @api.model
    def _get_report_values(self, docids, data=None):
        if self.env.context.get('inventory_pdf_report') and data:
            report_data = data.get('report_data') or {}
            data.update({
                'report_main_line_data': report_data.get('report_lines', []),
                'Filters': report_data.get('filters', {}),
                'Dates': report_data.get('orders', {}),
                'company': self.env.company,
            })
        return data
