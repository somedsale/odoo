{
    'name': 'Custom Sale Report',
    'version': '1.0',
    'summary': 'Generate sale quotation report by week, month, or quarter in PDF',
    'category': 'Sales',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_report_template.xml',
        'views/wizard_view.xml',
    ],
    'installable': True,
    'application': False,
}