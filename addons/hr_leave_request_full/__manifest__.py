# -*- coding: utf-8 -*-
{
    'name': 'Somed - Xin nghỉ phép',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Quản lý đơn xin nghỉ phép, luồng duyệt và in PDF',
    'author': 'Somed',
    'depends': ['base', 'mail', 'hr'],
    'data': [
        'security/leave_request_security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
        # Report phải load trước views vì form view có button %(action_report_somed_leave_request)d
        'reports/leave_request_report.xml',
        'views/reject_wizard_views.xml',
        'views/leave_request_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
