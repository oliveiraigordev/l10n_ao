import math
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
import re


class TaxExemptionReason(models.Model):
    _name = "tax.exemption.reason"

    _description= " Este modelo representa os motivos de isenção de Imposto IVA"

    name = fields.Char("Menção na factura")
    code = fields.Char("Code")
    reason = fields.Char("Motivo")


