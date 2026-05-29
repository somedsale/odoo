# -*- coding: utf-8 -*-
{
    'name': 'Somed - Tạm ứng',
    'version': '17.0.1.0.3',
    'summary': 'Quản lý giấy đề nghị tạm ứng, luồng duyệt và in PDF',
    'description': 'Module đề nghị tạm ứng: nhân viên tạo phiếu, trưởng bộ phận duyệt, kế toán tổng hợp duyệt, giám đốc duyệt, thông báo và in PDF.',
    'category': 'Human Resources',
    'author': 'Somed',
    'depends': ['base', 'mail', 'hr', 'account', 'custom_account_payment_request'],
    'data': [
        'security/advance_request_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'data/paperformat.xml',
        'views/advance_request_views.xml',
        'views/reject_wizard_views.xml',
        'reports/advance_request_report.xml',
    ],
    'installable': True,
    'application': True,
    'images': ['static/description/icon.png'],
    'license': 'LGPL-3',
}
