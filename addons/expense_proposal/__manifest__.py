{
    'name': 'Expense Proposal',
    'version': '1.0',
    'summary': 'Module for managing expense proposals in accounting',
    'author': 'Your Name',
    'category': 'Accounting',
    'depends': ['account', 'base', 'custom_account_payment_request', 'web','report_daily_cash_flow','bank_balance'],  # Phụ thuộc vào module kế toán
    'data': [
        'security/ir.model.access.csv',
        'data/sequence_data.xml',
        'data/proposal_sheet_state_option.xml',
        'views/expense_proposal_line_form.xml',
        'views/expense_proposal_views.xml',
        # 'views/account_payment_request_views.xml',
        'wizard/planned_payment_wizard_views.xml',
        'reports/report_pending_approval.xml',
        'reports/report_approved_unpaid_template.xml',
        'reports/paperformat_expense_proposal.xml',
        'reports/report_expense_proposal.xml',
        'reports/report_expense_proposal_template.xml',
        'reports/pending_payment_wizard_report.xml',
        'reports/report_planned_payment.xml',
        'wizard/view_wizard.xml',
        'wizard/pending_report_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'expense_proposal/static/src/css/style.css',
        ],
    },
    'installable': True,
    'application': True,
}