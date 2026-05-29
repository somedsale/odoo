# -*- coding: utf-8 -*-
{
    'name': 'Somed - Xin nghỉ phép',
    'version': '17.0.1.1.0',
    'category': 'Human Resources',
    'summary': 'Quản lý đơn xin nghỉ phép, duyệt nhiều cấp và in PDF',
    'author': 'Somed',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/leave_request_views.xml',
        'views/reject_wizard_views.xml',
        'reports/leave_request_report.xml',
    ],
    'installable': True,
    'application': True,
}
