from odoo import fields, api, models
from collections import deque

class PosSaftWizard(models.TransientModel):

    _inherit = "angola.saft.wizard"


    def get_pos_taxes(self):

        pos_invoices = self.env["pos.order"].search([("date_order", ">=", fields.Date.to_string(self.date_start)),
                                                     ("system_entry_date", "!=", None),
                                                     ("date_order", "<=", fields.Date.to_string(self.date_end)),
                                                     ("state", "in", ["done", "paid"])],
                                                    order="system_entry_date asc")
        pos_invoices_taxes = pos_invoices.mapped("lines").mapped("tax_ids")
        pos_invoices_taxes = pos_invoices_taxes.filtered(
            lambda r: r.tax_type in ['IVA','NS'] and not r.is_withholding)
        return pos_invoices_taxes


    def get_pos_saft(self, invoice_saft):

         orders = self.env["pos.order"].search(
             [("date_order", ">=", fields.Date.to_string(self.date_start)),
              ("date_order", "<=", fields.Date.to_string(self.date_end)),
              ("system_entry_date", "!=", None),
              ], order="system_entry_date asc,date_order asc")
         result = {}
         if orders:
             pos_saft = orders.get_saft_data().get("SalesInvoices")
             for key, value in invoice_saft.copy().items():
                 if isinstance(value, int) or isinstance(value, float):
                     result[key] = round(pos_saft[key] + invoice_saft[key], 2)
                 elif isinstance(value, list):
                     result[key] = pos_saft[key] + invoice_saft[key]


             print(result)
         elif invoice_saft:
             result = invoice_saft

         return result


    def get_pos_partners(self):
        orders = self.env["pos.order"].search(
            [("date_order", ">=", fields.Date.to_string(self.date_start)),
             ("date_order", "<=", fields.Date.to_string(self.date_end)),
             ("system_entry_date", "!=", None),
             ], order="system_entry_date asc")

        partners = orders.mapped('partner_id')

        if partners:
            return partners


    def get_pos_products(self):
        orders = self.env["pos.order"].search(
            [("date_order", ">=", fields.Date.to_string(self.date_start)),
             ("date_order", "<=", fields.Date.to_string(self.date_end)),
             ("system_entry_date", "!=", None),
             ], order="system_entry_date asc")

        products = orders.mapped('lines.product_id')
        if products:
            return products

