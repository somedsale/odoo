{
    'name': 'Accounting Payment Request',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Yêu cầu chi tiền dựa trên phiếu đề xuất vật tư',
    'author': 'Somed',
    'depends': ['base', 'account', 'proposal_sheet','custom_account_menu','web'],
    'data': [
        'data/ir_sequence_data.xml',
        'security/ir.model.access.csv',
        'views/account_payment_request_views.xml',
        'views/proposal_sheet_inherit_payment_view.xml'
    ],
    'installable': True,
    'auto_install': False,
}