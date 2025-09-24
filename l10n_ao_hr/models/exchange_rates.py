from odoo import fields, models, api, _


class HRExchangeRates(models.Model):
    _name = 'hr.exchange.rate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Employee Exchange Rates'

    name = fields.Float('Taxa de Câmbio')
    date = fields.Date('Data de Registo', readonly=1, default=fields.Date.context_today)
    active_use = fields.Boolean('Activo')
