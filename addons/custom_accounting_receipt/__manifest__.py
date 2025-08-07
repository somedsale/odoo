{
    'name': 'Phiếu Thu Kế Toán',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Module quản lý phiếu thu kế toán trong Odoo',
    'description': """
        Module này thêm chức năng quản lý phiếu thu kế toán.
        - Tạo và quản lý phiếu thu
        - Ghi sổ bút toán kế toán tự động
        - Hỗ trợ các trạng thái Nháp, Đã ghi sổ, Đã hủy
    """,
    'author': 'Your Name',
    'depends': ['account', 'mail', 'project', 'web', 'custom_account_menu'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/account_receipt_views.xml',
    ],
    'installable': True,
    'auto_install': False,
}