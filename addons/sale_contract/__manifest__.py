{
    'name': 'Sale Contract',
    'version': '1.0',
    'summary': 'Module to manage Sale Contracts similar to Sale Quotations',
    'description': """
        This module allows creating and managing sale contracts with PDF output similar to Odoo Sale Quotations.
    """,
    'category': 'Sales',
    'depends': ['base', 'sale', 'mail'],
    'data': [
        'views/sale_contract_views.xml',
        'report/sale_contract_report.xml',
        'data/sale_contract_data.xml',
        'templates/sale_contract_template.xml',
    ],
    'installable': True,
    'application': True,
}