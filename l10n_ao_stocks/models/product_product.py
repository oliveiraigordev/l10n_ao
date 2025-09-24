# models/product_product.py
import logging
from odoo import models

class ProductProduct(models.Model):
    _inherit = 'product.product'

    def _get_product_accounts(self):
        self.ensure_one()
        res = super()._get_product_accounts()


        tmpl = self.product_tmpl_id.with_company(self.env.company)
        if tmpl.use_product_stock_account:
            if tmpl.stock_input_account_id:
                res['stock_input'] = tmpl.stock_input_account_id.id
            if tmpl.stock_output_account_id:
                res['stock_output'] = tmpl.stock_output_account_id.id
            if tmpl.stock_valuation_account_id:
                res['stock_valuation'] = tmpl.stock_valuation_account_id.id

        if not res.get('stock_input'):
            cat_input = tmpl.categ_id.property_stock_account_input_categ_id
            if cat_input:
                res['stock_input'] = cat_input.id

        if not res.get('stock_input') and self.env.context.get('location_dest_id'):
            location = self.env['stock.location'].browse(self.env.context['location_dest_id'])
            if location and location.account_input_id:
                res['stock_input'] = location.account_input_id.id
        return res
