from odoo import models, api

class SaleContractReport(models.AbstractModel):
    _name = 'report.custom_sale_contract.report_sale_contract_document'
    _description = 'Sale Contract Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['sale.contract'].browse(docids)
        if not docs:
            raise ValueError("No sale contract record found for the report.")
        return {
            'doc_ids': docids,
            'doc_model': 'sale.contract',
            'docs': docs,
            'o': docs[0] if docs else None,  # Truyền đối tượng đầu tiên dưới dạng 'o'
        }