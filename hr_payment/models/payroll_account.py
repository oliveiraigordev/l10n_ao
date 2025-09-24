from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools import float_is_zero

class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _prepare_slip_lines(self, date, line_ids):
        self.ensure_one()
        precision = self.env['decimal.precision'].precision_get('Payroll')
        new_lines = []

        for line in self.line_ids.filtered(lambda line: line.category_id):
            amount = line.total

            # 🔁 Se for Angola e a linha for BASE, substitui o valor pelo total líquido
            if self.env.company.country_id.code == 'AO' and line.code == 'BASE':
                print("🔁 Substituindo BASE pelo total_paid:", self.total_paid)
                amount = self.total_paid or 0.0

            if line.code == 'NET':
                for tmp_line in self.line_ids.filtered(lambda l: l.category_id):
                    if tmp_line.salary_rule_id.not_computed_in_net:
                        if amount > 0:
                            amount -= abs(tmp_line.total)
                        elif amount < 0:
                            amount += abs(tmp_line.total)

            if float_is_zero(amount, precision_digits=precision):
                continue

            debit_account_id = line.salary_rule_id.account_debit.id
            credit_account_id = line.salary_rule_id.account_credit.id

            if debit_account_id:
                debit = abs(amount)
                credit = 0.0
                # debit = amount if amount > 0.0 else 0.0
                # credit = -amount if amount < 0.0 else 0.0

                debit_line = self._get_existing_lines(
                    line_ids + new_lines, line, debit_account_id, debit, credit)

                if not debit_line:
                    debit_line = self._prepare_line_values(line, debit_account_id, date, debit, credit)
                    debit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_debit.tax_ids.ids]
                    new_lines.append(debit_line)
                else:
                    debit_line['debit'] += debit
                    debit_line['credit'] += credit

            if credit_account_id:
                debit = 0.0
                credit = abs(amount)

                credit_line = self._get_existing_lines(
                    line_ids + new_lines, line, credit_account_id, debit, credit)

                if not credit_line:
                    credit_line = self._prepare_line_values(line, credit_account_id, date, debit, credit)
                    credit_line['tax_ids'] = [(4, tax_id) for tax_id in line.salary_rule_id.account_credit.tax_ids.ids]
                    new_lines.append(credit_line)
                else:
                    credit_line['debit'] += debit
                    credit_line['credit'] += credit

        return new_lines

    # def write(self, vals):
    #     """
    #     Impede qualquer alteração em um payslip cujo lançamento contábil
    #     (move_id) já esteja postado. Exibe mensagem pedindo para reverter
    #     o movimento antes de editar o recibo.
    #     """
    #     for slip in self:
    #         # Se existir move contábil e ele estiver postado:
    #         if slip.move_id and slip.move_id.state == 'posted':
    #             raise UserError(_(
    #                 "Os recibos já possuem movimentos na contabilidade. "
    #                 "Por favor, altere o lançamento para rascunho antes de prosseguir."
    #             ))
    #     # Se não houver problemas, chama o método original
    #     return super(HrPayslip, self).write(vals)
