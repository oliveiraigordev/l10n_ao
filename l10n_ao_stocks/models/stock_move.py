import logging
from odoo import models
from odoo.tools import float_is_zero

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _get_price_unit(self):
        self.ensure_one()
        super_price = super()._get_price_unit()
        prec = self.env['decimal.precision'].precision_get('Product Price')

        price = super_price

        if float_is_zero(price, precision_digits=prec) and self._is_in():
            po_line = getattr(self, 'purchase_line_id', False)
            if po_line:
                try:
                    po_price = po_line._get_stock_move_price_unit()
                    price = po_price
                except Exception:
                    po_price = po_line.price_unit or 0.0
                    price = po_price

        if float_is_zero(price, precision_digits=prec):
            price = self.product_id.standard_price or 0.0

        return price

    def _should_create_valuation(self):
        self.ensure_one()
        tmpl = self.product_id.product_tmpl_id
        if tmpl.use_product_stock_account:
            return tmpl.stock_valuation == 'real_time'
        return super()._should_create_valuation()

    def _get_in_svl_vals(self, forced_quantity):
        svl_vals_list = []
        for move in self:
            move = move.with_company(move.company_id)
            valued_qty = 0.0
            for line in move._get_in_move_lines():
                valued_qty += line.product_uom_id._compute_quantity(line.qty_done, move.product_id.uom_id)
            if move.product_id.cost_method == 'standard':
                unit_cost = move.product_id.standard_price
                if float_is_zero(unit_cost, precision_rounding=move.company_id.currency_id.rounding):
                    unit_cost = abs(move._get_price_unit())
            else:
                unit_cost = abs(move._get_price_unit())

            svl_vals = move.product_id._prepare_in_svl_vals(forced_quantity or valued_qty, unit_cost)
            svl_vals.update(move._prepare_common_svl_vals())
            if forced_quantity:
                svl_vals['description'] = 'Correction of %s (modification of past move)' % (move.picking_id.name or move.name)
            svl_vals_list.append(svl_vals)
        return svl_vals_list
