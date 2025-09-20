# -*- coding: utf-8 -*-
{
    'name' : 'Channel Notification',
    'version' : '17.0.1.0',
    'summary': 'Channel Notification',
    'sequence': 10,
    'description': '''
        Channel Notification
    ''',
    'category': 'Productivity/Discuss',
    'assets':{
        "web.assets_backend": [
            '/sttl_channel_notification/static/src/components/composer/composer.js',
            '/sttl_channel_notification/static/src/models/discuss_sidebar_category_item.js'
        ],
    },
    'depends': ['web', 'mail'],   
    'installable': True,
    'application': False,
    "price": 0,
    "author": "Silver Touch Technologies Limited",
    "website": "https://www.silvertouch.com/",
    'images': ['static/description/banner.png'],
    "currency": "USD",
    'license': 'LGPL-3',
}
