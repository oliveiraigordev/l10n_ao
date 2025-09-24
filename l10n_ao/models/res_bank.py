from odoo import models, fields


class ResPartnerBankAng(models.Model):
    _inherit = "res.partner.bank"

    show_document = fields.Boolean("Show on documents")
    acc_iban = fields.Char("IBAN")
    show_doc = fields.Boolean("Show")


class ResBank(models.Model):
    _inherit = "res.bank"

    code = fields.Char("Code", size=6)

    _sql_constraints = [
        ('name_code_uniq', 'unique(code)', 'The code of the bank must be unique!')
    ]
