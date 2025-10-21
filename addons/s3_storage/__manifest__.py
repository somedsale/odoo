# -*- coding: utf-8 -*-
{
    "name": "Somed S3 Cloud Storage",
    "summary": "Lưu trữ ir.attachment trên Amazon S3 / S3-compatible",
    "version": "17.0.1.0.0",
    "category": "Technical",
    "license": "LGPL-3",
    "author": "Somed",
    "website": "",
    "depends": ["base", "web", 'mail'],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
    ],
    "external_dependencies": {"python": ["boto3"]},
    "installable": True,
}
