# -*- coding: utf-8 -*-
{
    "name": "Community Documents",
    "version": "17.0.1.0.0",
    "category": "Productivity",
    "summary": "Lightweight document management for Odoo 17 Community (Folders/Tags/Sharing)",
    "depends": ["base", "mail", "portal", "web"],
    "data": [
        # "security/groups.xml",
        # "security/security.xml",
        "security/ir.model.access.csv",
        "data/sequence.xml",
        # "data/default_folder.xml",
        "views/document_folder_views.xml",
        "views/document_tag_views.xml",
        "views/document_document_views.xml",
        "views/document_share_views.xml",
        "views/document_share_templates.xml",
        "views/document_create_folder_wizard_views.xml",
        "views/document_add_link_wizard_views.xml",
        "views/document_client_action.xml",
        "views/document_menus.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "community_documents/static/src/scss/document_dashboard.scss",
            "community_documents/static/src/js/document_dashboard.js",
            "community_documents/static/src/xml/document_dashboard.xml",
        ],
    },
    "application": True,
    "license": "LGPL-3",
}
