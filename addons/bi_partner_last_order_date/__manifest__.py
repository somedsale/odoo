# -*- coding: utf-8 -*-
# Part of BrowseInfo. See LICENSE file for full copyright and licensing details.
{
    'name': "Partner Order History in Odoo | Track Last Orders Date | Partner Last Order Date in Odoo",
    'version': '17.0.0.0',
    'category': 'Sales',
    'summary': "View Last Order Dates Instantly Partner last Order date and name track Order history tracking Sale and purchase data order dates last sale order last purchase order date Confirmed order date Order management Report Last sale order date previous order date",
    'description': """Partner Last Order Date Odoo app helps businesses easily see the last time they sold something to a customer or bought something from a supplier. This information shows up right on the customer or supplier's page in Odoo. Knowing when the last transaction happened helps businesses follow up with customers they haven't heard from in a while and make smarter decisions about what to buy. The app automatically keeps track of the latest sales and purchase orders, so the information is always up-to-date. It's a simple tool that makes it easier for businesses to manage their customers and suppliers and keep track of their interactions.""",
    'author': 'BROWSEINFO',
    'website': 'https://www.browseinfo.com/demo-request?app=bi_partner_last_order_date&version=17&edition=Community',
    'depends': ['base','sale_management','purchase'],
    'data': [
       'views/res_partner_view.xml'
    ],
    'assets': {
       
    },
    'license':'OPL-1',
    'installable': True,
    'auto_install': False,
    'live_test_url':'https://www.browseinfo.com/demo-request?app=bi_partner_last_order_date&version=17&edition=Community',
    "images":['static/description/Banner.gif'],
}

