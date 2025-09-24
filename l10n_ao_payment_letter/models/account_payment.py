from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime

class AccountPaymentInherit(models.Model):
    _inherit = 'account.payment'

    format_date = fields.Char(string="Data Formatada")
    count_seq = fields.Integer(string='Sequencia', default=0)
    format_seq = fields.Char(string="Sequencia Formatada")


    def action_letter_payment(self):
        for record in self:
            format = self.env['report.paperformat'].search([('name', '=', "A4 Tis Tech")])

            meses = [
                "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]
            mes_numero = record.date.month
            nome_do_mes = meses[mes_numero]
            data = f"{record.date.day} de {nome_do_mes} de {record.date.year}."

            record.count_seq = 1 + record.count_seq
            # Número da sequência
            sequencia = record.count_seq  # você pode alterar este valor conforme necessário

            # Ano atual
            ano_atual = datetime.now().year

            # Formatar a sequência para que tenha sempre 3 dígitos, seguido pelo ano
            sequencia_formatada = f"{sequencia:03d}/{ano_atual}"
            record.format_date = data
            record.format_seq = sequencia_formatada

        return self.env.ref('l10n_ao_payment_letter.report_letter_payment_pdf').report_action(self)