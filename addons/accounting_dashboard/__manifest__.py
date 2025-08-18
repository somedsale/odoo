{
    "name": "Accounting Dashboard",
    "summary": "Dashboard kế toán: Phiếu thu/chi/đề xuất, dòng tiền & chi phí theo dự án",
    "version": "17.0.1.0",
    "category": "Accounting",
    "author": "You",
    "depends": [ "project", "mail"],
    "data": [
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "accounting_dashboard/static/src/js/**/*.js",
            "accounting_dashboard/static/src/xml/**/*.xml",
            
        ],
},
    "installable": True,
    "application": True,
}
