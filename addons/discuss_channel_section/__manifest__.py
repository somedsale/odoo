# -*- coding: utf-8 -*-
{
    "name": "Discuss Channel Section",
    "version": "17.0.1.0.0",
    "summary": "Allow users to organize discuss channels into custom sections",
    "category": "Discuss",
    "author": "Your Company",
    "license": "LGPL-3",
    "depends": [
        "mail",
    ],
    "data": [
        "security/discuss_channel_section_security.xml",
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "discuss_channel_section/static/src/js/discuss_sidebar_sections_patch.js",
            "discuss_channel_section/static/src/xml/discuss_sidebar_sections.xml",
        ],
    },
    "installable": True,
    "application": False,
}