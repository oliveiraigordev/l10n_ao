from odoo import fields, models, api, _
from odoo.exceptions import Warning, UserError, ValidationError


class SalaryRecordRules(models.Model):
    _inherit = 'hr.salary.rule'

    is_irt_compensation = fields.Boolean('Para cálculos de compensação IRT')
    cool_parcel = fields.Float('Parcela Fixa')
    # is_calculating_to_dollar = fields.Boolean('Para conversão de KZ => Dollar')
    is_suffer_absence_discounts = fields.Boolean('Sofrer descontos por faltas')
    excess_amount = fields.Float('Valor de Excesso dos Subsídios', default=30000)
    irt_tax = fields.Float('Taxa IRT')
    paid_in_kwanza_in_angola = fields.Boolean('Abono Recebidos em Kwanzas em Angola')
    paid_in_kwanza_foreign_currency = fields.Boolean('Abono a ser pago em moeda estrageira')
    inss_rule = fields.Boolean('Abono Sujeito a INSS')
    inss_tax = fields.Float('Taxa INSS', default=3)
    inss8_tax = fields.Float('Taxa INSS 8%', default=8)

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            if values.get("code") and self.code in ['BASE', 'CHEF', 'NAT', 'PREM', 'REPR', 'ATA', 'sub_not', 'FER',
                                                    'CORES', 'sub_ren_casa', 'RENDES', 'FALH', 'FAMI', 'TRAN', 'ALIM',
                                                    'FALTA', 'ATRA', 'FJNR', 'FI', 'HEXTRA_50', 'HEXTRA_75', 'R188',
                                                    'R189',
                                                    'R185', 'R20']:
                return {}
        return super(SalaryRecordRules, self).write(values)

    def unlink(self):
        for record in self:
            if self.env.company.country_id.code == "AO":
                if record.code in ['BASE', 'CHEF', 'NAT', 'PREM', 'REPR', 'ATA', 'sub_not', 'FER',
                                   'CORES', 'sub_ren_casa', 'RENDES', 'FALH', 'FAMI', 'TRAN', 'ALIM', 'FALTA',
                                   "SAL_FER",
                                   "GRATIF_FER", 'ATRA', 'FJNR', 'FI', 'HEXTRA_50', 'HEXTRA_75', 'R188', 'R189',
                                   'R185', 'R20']:
                    return {}

            return super(SalaryRecordRules, record).unlink()
