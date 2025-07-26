{
    'name': 'Internal Accounting',
    'version': '1.0',
    'category': 'Kế Toán Nội Bộ',
    'summary': 'Quản lý phiếu thu chi nội bộ',
    'author': 'Your Name',
    'depends': ['base','proposal_sheet'],
    'data': [
        'security/security.xml',  
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/internal_payment_views.xml',
    ],
    'installable': True,
    'application': True,
}
