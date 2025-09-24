from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.l10n_ao.sign import sign
import datetime
import logging

_logger = logging.getLogger(__name__)


class PosSessions(models.Model):
    _inherit = 'pos.session'

    def session_orders(self):
        orders = self.env["pos.session"].search([('id', '=', self.id)]).order_ids
        data = [{'order': len(orders),
                 'tax': sum(orders.mapped("amount_tax")),
                 'total': sum(orders.mapped("amount_total"))}]

        return data

    def credit_notes_session(self):
        orders = self.env["pos.session"].search([('id', '=', self.id)]).order_ids.filtered(lambda r: r.amount_total < 0)
        data = [{'order': len(orders),
                 'tax': sum(orders.mapped("amount_tax")),
                 'total': sum(orders.mapped("amount_total"))}]
        return data


    def total_user_amount(self):
        orders = self.env["pos.session"].search([('id', '=', self.id)]).order_ids
        datas = []
        users = orders.mapped("employee_id")
        for user in users:
            order = orders.filtered(lambda r: r.employee_id == user)
            lines = order.lines
            data = {'user': user.name,
                    'qty': sum(lines.mapped("qty")),
                    'total': sum(order.mapped("amount_total"))}
            datas.append(data)

            def get_total(data):
                return data.get("total")
            datas = sorted(datas, key=get_total, reverse=True)
        return datas


    def product_quantity(self):
        orders = self.env["pos.session"].search([('id', '=', self.id)]).order_ids
        products = orders.lines.mapped("product_id")
        lines = orders.mapped("lines")
        datas = []
        for p in products:
            ln = lines.filtered(lambda r: r.product_id == p)
            data = {'name': p.name,
                    'total': sum(ln.mapped("qty")),
                    'total_sold': sum(ln.mapped("price_subtotal_incl"))}
            datas.append(data)

            def get_total_sold(data):
                return data.get("total")

            datas = sorted(datas, key=get_total_sold, reverse=True)

        return datas[:5] if not self.env['ir.config_parameter'].sudo().get_param(
            'dont_validate_product_quantity') else datas

    def _loader_params_res_company(self):
        return {
            'search_params': {
                'domain': [('id', '=', self.company_id.id)],
                'fields': [
                    'currency_id', 'email', 'website', 'company_registry', 'vat', 'name', 'phone', 'partner_id',
                    'country_id', 'state_id', 'tax_calculation_rounding_method', 'nomenclature_id', 'point_of_sale_use_ticket_qr_code',
                    'street', 'city', 'street2', 'zip',
                ],
            }
        }

    def total_payment_method(self):
        orders = self.env["pos.session"].search([('id', '=', self.id)]).order_ids
        payments = orders.mapped("payment_ids")
        payment_methods = orders.payment_ids.mapped("payment_method_id")
        datas = []
        for method in payment_methods:
            pays = payments.filtered(lambda r: r.payment_method_id == method)
            data = {
                'method': method.name,
                'total_paid': sum(pays.mapped("amount"))
            }
            datas.append(data)
        return datas
