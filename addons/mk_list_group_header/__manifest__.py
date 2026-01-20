# -*- coding: utf-8 -*-
{
    "name": "MK List Group Header (2-tier header)",
    "version": "17.0.1.0.0",
    "category": "Web",
    "summary": "Add a grouped header row above list headers, activated by field options header_option/header_group",
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "mk_list_group_header/static/src/js/list_group_header.js",
            # "mk_list_group_header/static/src/scss/list_group_header.scss",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}
