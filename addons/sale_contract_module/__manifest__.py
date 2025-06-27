{
    'name': "Sale Contract Management",
    'summary': "Module to create and manage sale contracts with PDF export",
    'description': """
        This module allows users to create sale contracts linked to sale orders
        and generate PDF reports for these contracts.
    """,
    'author': "Cuong Dev",
    'category': 'Sales',
    'version': '1.0',
    'depends': ['base', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_contract_views.xml',
        'reports/sale_contract_report.xml',
        'data/sale_contract_data.xml',
    ],
    'installable': True,
    'application': True,
}