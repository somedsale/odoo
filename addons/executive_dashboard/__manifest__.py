# -*- coding: utf-8 -*-
{
    "name": "Executive Dashboard",
    "summary": "Bảng điều khiển tổng hợp cho Giám đốc",
    "version": "1.0",
    "category": "Dashboard",
    "author": "Somed Dev",
    "depends": ["base", "web", "sale", "account", "hr", "project","custom_director_role"],
    "data": [
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js",
            "executive_dashboard/static/src/js/**/*.js",
            "executive_dashboard/static/src/xml/**/*.xml",
            "executive_dashboard/static/src/scss/**/*.scss",
        ],
    },
    "application": True,
}
