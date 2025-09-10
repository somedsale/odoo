{
    'name': 'Expense Proposal',
    'version': '1.0',
    'summary': 'Module for managing expense proposals in accounting',
    'author': 'Your Name',
    'category': 'Accounting',
    'depends': ['account', 'base', 'custom_account_payment_request', 'web'],  # Phụ thuộc vào module kế toán
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'views/expense_proposal_line_form.xml',
        'views/expense_proposal_views.xml',
        'views/account_payment_request_views.xml',
        'reports/report_pending_approval.xml',
        'reports/report_approved_unpaid_template.xml'
    ],
    'installable': True,
    'application': True,
}