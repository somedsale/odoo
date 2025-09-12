{
    'name': 'Project Payment Schedule',
    'version': '1.0',
    'category': 'Project',
    'summary': 'Quản lý thanh toán từng đợt theo dự án',
    'depends': ['base', 'project', 'mail','custom_accounting_receipt'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_payment_schedule_views.xml',
    ],
    'installable': True,
    'application': False,
}
