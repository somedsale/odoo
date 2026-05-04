# -*- coding: utf-8 -*-
{
    'name': 'Proposal Commercial Purchase',
    'version': '17.0.1.0.0',
    'category': 'Operations',
    'summary': 'Thêm loại đề xuất mua hàng thương mại theo Sale Order',
    'depends': [
        'base',
        'sale_management',
        'purchase',
        'project',
        'stock',
        'account',
        'proposal_sheet',
    ],
    'data': [
        'views/proposal_commercial_purchase_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}