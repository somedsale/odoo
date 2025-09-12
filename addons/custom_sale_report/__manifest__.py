{
    'name': 'Custom Sale Report',
    'version': '1.0',
    'summary': 'Generate sale quotation report for selected week, month, and quarter with contracts in PDF or HTML',
    'category': 'Sales',
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_report_template.xml',
        'views/wizard_view.xml',
        'views/report_history_view.xml',
    ],
    'installable': True,
    'application': False,
}