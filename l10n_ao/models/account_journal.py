import math
from odoo import fields, models, api, _
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
import re


class AccountJournalAng(models.Model):
    _inherit = "account.journal"

    _sql_constraints = [
        ('code_company_uniq', 'unique(code, company_id)',
         'The code and name of the journal must be unique per company !'),
    ]

    document_type = fields.Selection(
        [('FT', 'Factura'), ('FR', 'Factura Recibo'), ('VD', 'Venda a Dinheiro'), ('GF', 'Factura Genérica'),
         ('GF', 'Factura Genérica'), ('FG', 'Factura Global'), ('AC', 'Aviso de cobrança'),
         ], string="Document Type")
    # prefix_sequence = fields.Char(string="Prefix Sequence")
    auto_invoicing = fields.Boolean(_("Auto Invoicing"))
    journal_ao_id = fields.Many2one("account.journal.ao")
    is_settlement = fields.Boolean(string="É um diário de Resultados?",
                                   help="Diários de Resultado são utilizados no apuramento de resultados")
    settlement_type = fields.Selection([('M14', "Mês 14"), ('M15', "Mês 15"),],
                                       string="Tipo de Apuramento de Resultado")

    @api.onchange("type")
    def change_journal_code(self):
        if self.type == 'purchase':
            self.code = 'FTF'

    def write(self, vals):
        if self[0].company_id.country_id.code == "AO":
            if vals.get('type') in ['sale', 'purchase']:
                self.write({'refund_sequence': True, "restrict_mode_hash_table": True})
            if re.search(r"\s", str(vals.get("code"))):
                raise ValidationError(
                    _("O código curto não pode ter espaço. Por favor Retire qualquer espaço que tenha adicionado!"))
        result = super(AccountJournalAng, self).write(vals)

    @api.model_create_multi
    def create(self, vals):
        journal = super(AccountJournalAng, self).create(vals)
        if vals:
            if vals[0].get('type') in ['sale', 'purchase'] and journal.company_id.country_id.code == "AO":
                journal.write({'refund_sequence': True, "restrict_mode_hash_table": True})
        return journal
