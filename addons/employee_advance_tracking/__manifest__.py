{
    'name': 'Employee Advance Tracking',
    'version': '1.0',
    'summary': 'Theo dõi tạm ứng nhân viên cho kế toán',
    'description': """
Quản lý và theo dõi tạm ứng nhân viên:
- Ghi nhận tổng tiền tạm ứng, hoàn ứng, còn lại.
- Cập nhật tự động khi có giải chi và phiếu thu hoàn ứng.
    """,
    'author': 'Somed',
    'category': 'Accounting',
    'depends': ['hr', 'customer_account_payment_proposal','custom_account_payment_request','custom_accounting_receipt'],  # module gốc có account.payment.proposal
    'data': [
        'security/ir.model.access.csv',
        'views/account_employee_advance_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'employee_advance_tracking/static/src/css/style.css',
        ],
    },
    'installable': True,
    'application': False,
}
