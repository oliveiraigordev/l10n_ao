from odoo import models,fields, api

class TaxRegimeVat(models.Model):
    _name = "account.tax.regime"
    _description="Regimes De Imposto Iva"


    name = fields.Char(string="Regime", required=True)
