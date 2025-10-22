# -*- coding: utf-8 -*-
{
    "name": "Somed Document S3",
    "summary": "Xem/Tải tài liệu lưu trên S3 (độc lập với ir.attachment)",
    "version": "17.0.1.0.0",
    "author": "Somed",
    "license": "LGPL-3",
    "depends": ["base", "web"],
    "data": [
        "security/ir.model.access.csv",
        "views/document_s3_views.xml",
    ],
    "installable": True,
    "application": False,
}
