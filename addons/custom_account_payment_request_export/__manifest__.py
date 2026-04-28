{
    'name': 'Account Payment Request XLSX EXPORT',
    'version': '1.0',
    'summary': 'Export Account Payment Request',
    'author': 'Your Name',
    'category': 'Custom',
    'depends': ['base', 'report_xlsx', 'custom_account_payment_request'],  # thay bằng module proposal sheet của bạn
    'data': [
        'views/account_payment_request_report.xml',
        'views/payment_request_pdf_template.xml',
    ],
    'installable': True,
    'application': False,
}
