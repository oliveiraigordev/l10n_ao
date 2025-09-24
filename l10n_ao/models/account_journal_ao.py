import math
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
import re


class AccountJournalAngAo(models.Model):
    _name = "account.journal.ao"

    name = fields.Char("Journal Name")
    code = fields.Integer("Number of Journal")
    sequence_id = fields.Many2one("ir.sequence")

    _sql_constraints = [
        ('code_journal_ao_uniq', 'unique(code)',
         'O código de diário Deve ser Único!'),
    ]