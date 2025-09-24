from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError


class ProductCategory(models.Model):
    _inherit = 'product.category'



    @api.constrains('property_stock_valuation_account_id', 'property_stock_account_output_categ_id', 'property_stock_account_input_categ_id')
    def _check_valuation_accouts(self):
        # Prevent to set the valuation account as the input or output account.
        for category in self:
            valuation_account = category.property_stock_valuation_account_id
            input_and_output_accounts = category.property_stock_account_input_categ_id | category.property_stock_account_output_categ_id
            if valuation_account and valuation_account in input_and_output_accounts:
                ...
                #raise ValidationError(_('The Stock Input and/or Output accounts cannot be the same as the Stock Valuation account.'))

