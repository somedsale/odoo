{
    'name': 'Account Receipt XLSX EXPORT',
    'version': '1.0',
    'summary': 'Export Account Receipt',
    'author': 'Your Name',
    'category': 'Custom',
    'depends': ['base', 'report_xlsx', 'custom_accounting_receipt'],  
    'data': [
        'views/account_receipt_report.xml',
    ],
    'installable': True,
    'application': False,
}
