from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    cpf = fields.Char(string="CPF")
