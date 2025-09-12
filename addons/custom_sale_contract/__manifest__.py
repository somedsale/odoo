{
    'name': 'Custom Sale Contract',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Module to manage sale contracts with terms and PDF export',
    'description': """
        A custom module to create sale contracts similar to sale orders, 
        pulling data from quotations, allowing terms input, and PDF export.
    """,
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/sale_contract_views.xml',
        'views/sale_contract_templates.xml',
    ],
    'installable': True,
    'application': True,
}