# -*- coding: utf-8 -*-

from odoo import models, api


class ProductProduct(models.Model):
    _inherit = 'product.product'

    @api.model
    def get_stock_info_for_popup(self, product_id):
        """
        Get stock information for popup display (optimized)
        Returns product image and stock quantities by location
        """
        product_data = self.sudo().browse(product_id).read([
            'display_name', 'default_code', 'barcode',
            'list_price', 'standard_price', 'currency_id', 'image_128'
        ])

        if not product_data:
            return {
                'product_name': 'Product not found',
                'image': False,
                'locations': [],
                'total_available': 0,
                'total_reserved': 0,
            }

        product_data = product_data[0]

        quant_groups = self.env['stock.quant'].sudo().read_group(
            domain=[
                ('product_id', '=', product_id),
                ('location_id.usage', '=', 'internal'),
            ],
            fields=['quantity:sum', 'reserved_quantity:sum'],
            groupby=['location_id'],
            lazy=False
        )
        locations = []
        total_available = 0
        total_reserved = 0

        for group in quant_groups:
            location_id = group.get('location_id')
            if not location_id:
                continue

            location = self.env['stock.location'].browse(location_id[0] if isinstance(location_id, tuple) else location_id)
            quantity_sum = group.get('quantity', 0)
            reserved_sum = group.get('reserved_quantity', 0)
            available = quantity_sum - reserved_sum

            locations.append({
                'id': location.id,
                'name': location.complete_name,
                'available': round(available, 2),
                'reserved': round(reserved_sum, 2),
            })

            total_available += available
            total_reserved += reserved_sum

        locations.sort(key=lambda x: x['name'])

        currency_symbol = ''
        if product_data.get('currency_id'):
            currency_symbol = self.env['res.currency'].browse(product_data['currency_id'][0]).symbol or ''

        image_base64 = False
        if product_data.get('image_128'):
            image_base64 = product_data['image_128'].decode('utf-8')

        return {
            'product_name': product_data['display_name'],
            'default_code': product_data['default_code'] or '',
            'barcode': product_data['barcode'] or '',
            'sales_price': float(product_data.get('list_price') or 0.0),
            'cost': float(product_data.get('standard_price') or 0.0),
            'currency_symbol': currency_symbol,
            'image': image_base64,
            'locations': locations,
            'total_available': round(total_available, 2),
            'total_reserved': round(total_reserved, 2),
        }
