from odoo import api, models, fields, _
from odoo.exceptions import UserError, ValidationError
from datetime import date
import calendar


IVA_ACCOUNT_PREFIXES = ["3452", "3453"]
IVA_ACCOUNT_CODES = ["34551", "345611", "34571", "345811"]

IVA_PURCHASE_ACC = "34522"
IVA_SALE_ACC = "34531"
IVA_APURAMENTO_ACC = "34551"
IVA_TO_PAY_ACC = "34561"
IVA_TO_REVOCER_ACC = "34571"
IVA_REIMBURSEMENT_ACC = "34581"


class ApuramentoIva(models.Model):
    _name = "apuramento.iva"
    _order = "date_start desc"
    _description = "Apuramento Iva"

    name = fields.Char(string="Nome", compute="_compute_name")

    year = fields.Integer(string="Ano", default=lambda self: fields.Date.today().year)
    month = fields.Integer(string="Mês", default=fields.Date.today().month)
    day = fields.Integer(string="Dia", default=lambda self: fields.Date.today().day)

    date_start = fields.Date(string="Inicio", help="Inicio do Apuramento")
    date_end = fields.Date(string="Fim", help="Fim do Apuramento")

    journal_id = fields.Many2one(comodel_name="account.journal", string="Diário")
    # TODO In this module, all the records I've seen there's only one
    # object in this One2Many, so there's no reason for it to be a One2Many
    line_ids = fields.One2many(
        comodel_name="apuramento.iva.line",
        inverse_name="apuramento_iva_id",
        string="Apuramento Iva",
    )
    show_reimburse_report_iva = fields.Boolean(
        string="Mostrar Botao Reembolsar/Reportar IVA",
        compute="_compute_show_reimburse_report_iva",
    )
    show_reimburse_date = fields.Boolean(
        string="Mostrar Data de Reembolso", compute="_compute_show_reimburse_report_iva"
    )
    show_iva_report_date = fields.Boolean(
        string="Mostrar Data de Reportar IVA",
        compute="_compute_show_reimburse_report_iva",
    )
    reimbursement_date = fields.Date(string="Data do Reembolso")
    is_overdue = fields.Boolean(string="Fora do Prazo")
    iva_report_date = fields.Date(
        string="Data a Reportar IVA", default=lambda self: fields.Date.today()
    )

    @api.onchange('date_start', 'date_end')
    def _onchange_period_fill_month(self):
        """Ao definir o período, preenche month/year/day como sugestão.
        O usuário pode editar depois normalmente."""
        for rec in self:

            if not rec.date_start and not rec.date_end:
                continue

            base_date = rec.date_start or rec.date_end
            if base_date:
                rec.month = base_date.month
                rec.year = base_date.year
                rec.day = base_date.day


            if rec.date_start and rec.date_end and rec.date_start.month != rec.date_end.month:
                return {
                    'warning': {
                        'title': _("Período abrange meses diferentes"),
                        'message': _(
                            "O período selecionado vai de %(ds)s a %(de)s e abrange meses distintos. "
                            "O campo 'Mês' foi sugerido como %(m)s (com base no início), "
                            "mas você pode alterar manualmente.",
                        ) % {
                            'ds': rec.date_start,
                            'de': rec.date_end,
                            'm': rec.date_start.month,
                        }
                    }
                }
    
    @api.onchange('month', 'year')
    def _onchange_month_set_period(self):
        """Quando o usuário define o mês (e/ou ano), definir o período completo."""
        for rec in self:
            m = rec.month
            if not m:
                continue
            if m < 1 or m > 12:
                return {
                    'warning': {
                        'title': _("Mês inválido"),
                        'message': _("O campo 'Mês' deve estar entre 1 e 12.")
                    }
                }

            y = rec.year or (rec.date_start and rec.date_start.year) or (rec.date_end and rec.date_end.year) or fields.Date.today().year

            first_day = date(y, m, 1)
            last_day = date(y, m, calendar.monthrange(y, m)[1])

            rec.date_start = first_day
            rec.date_end = last_day

            rec.year = y
            rec.day = first_day.day

    def _compute_name(self):
        for iva in self:
            iva.name = f"Apuramento IVA {iva.day}-{iva.month}-{iva.year}"

    def _compute_show_reimburse_report_iva(self):
        for iva in self:
            if any(
                item.amount_to_recover > 0
                and not (item.amount_to_report > 0 or item.amount_reimburse > 0)
                for item in iva.line_ids
            ):
                iva.show_reimburse_report_iva = True
                iva.show_reimburse_date = True
                iva.show_iva_report_date = True
            elif any(item.amount_reimburse > 0 for item in iva.line_ids):
                iva.show_reimburse_report_iva = False
                iva.show_reimburse_date = True
                iva.show_iva_report_date = False
            elif any(item.amount_to_report > 0 for item in iva.line_ids):
                iva.show_reimburse_report_iva = False
                iva.show_reimburse_date = False
                iva.show_iva_report_date = True
            else:
                iva.show_reimburse_report_iva = False
                iva.show_reimburse_date = False
                iva.show_iva_report_date = False

    def action_view_iva(self):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "account.action_move_line_select"
        )
        account_ids = self.env["account.account"].search(
            [
                "|",
                "|",
                ("group_id.code_prefix_start", "in", IVA_ACCOUNT_PREFIXES),
                ("group_id.code_prefix_end", "in", IVA_ACCOUNT_PREFIXES),
                ("code", "in", IVA_ACCOUNT_CODES),
            ]
        )
        domain = [
            ("account_id", "in", account_ids.ids),
            ("move_id.invoice_date", ">=", self.date_start),
            ("move_id.invoice_date", "<=", self.date_end),
            ("move_id.state", "=", "posted"),
            ("tax_line_id.tax_type", "=", "IVA"),
        ]
        action.update(
            {
                "domain": domain,
                "display_name": "Itens de Diário",
                "context": {"search_default_posted": 1},
            }
        )
        return action

    def action_view_iva_move(self):
        if len(self.line_ids) == 1:
            return {
                "name": "Lançamento de IVA",
                "type": "ir.actions.act_window",
                "view_type": "form",
                "view_mode": "form",
                "res_model": "account.move",
                "res_id": self.line_ids.move_id.id,
            }

    def action_view_iva_reimburse_move(self):
        if len(self.line_ids) == 1:
            return {
                "name": "Lançamento de IVA",
                "type": "ir.actions.act_window",
                "view_type": "form",
                "view_mode": "form",
                "res_model": "account.move",
                "res_id": self.line_ids.reimburse_move_id.id,
            }

    def check_accounts_exists(self):
        account_codes = [
            IVA_PURCHASE_ACC,
            IVA_SALE_ACC,
            IVA_APURAMENTO_ACC,
            IVA_TO_REVOCER_ACC,
            IVA_TO_PAY_ACC,
            IVA_REIMBURSEMENT_ACC,
        ]
        for code in account_codes:
            if not self.get_account_by_code_prefix(code):
                raise UserError(f"Não foi encontrada conta com o código {code}")

    def get_account_by_code_prefix(self, code_prefix):
        # We want to find an account that starts with the code 'code_prefix'
        AccountAccount = self.env["account.account"]
        account_ids = AccountAccount.search([("code", "like", code_prefix)])
        for acc in account_ids:
            if acc.code[:len(code_prefix)] == code_prefix:
                return acc
        return AccountAccount

    def get_move_line_vals(
        self, debit_account_code, credit_account_code, amount, reverse_lines=False
    ):
        debit_acc_id = self.get_account_by_code_prefix(debit_account_code)
        credit_acc_id = self.get_account_by_code_prefix(credit_account_code)
        move_lines = [
            (
                0,
                0,
                {
                    "name": debit_acc_id.name,
                    "debit": abs(amount),
                    "account_id": debit_acc_id.id,
                },
            ),
            (
                0,
                0,
                {
                    "name": credit_acc_id.name,
                    "credit": abs(amount),
                    "account_id": credit_acc_id.id,
                },
            ),
        ]
        if reverse_lines:
            return list(reversed(move_lines))
        return move_lines

    def check_clearence_in_date_exists(self):
        all_clearences = self.env['apuramento.iva.line']
        clearences = all_clearences.search([
            ("apuramento_iva_id.date_start", "=", self.date_start),
            ("apuramento_iva_id.date_end", "=", self.date_end),
        ])
        
        return bool(clearences)


    def generate_account_move_iva(self):
        self.check_accounts_exists()
        if self.check_clearence_in_date_exists():
            raise UserError(_('Já existe um apuramento para a data informada'))

        move_ids = self.env["account.move"].search(
            [
                ("state", "=", "posted"),
                ("move_type", "in", ["out_invoice", "in_invoice"]),
                ("invoice_date", ">=", self.date_start),
                ("invoice_date", "<=", self.date_end),
            ]
        )
        tax_line_ids = move_ids.line_ids.filtered(
            lambda x: x.tax_line_id.iva_tax_type in  ('CAT50', 'CAT100', 'LIQ', 'DEDU', 'IS' )
        )
        tax_lines_sale = tax_line_ids.filtered(lambda x: x.credit)
        tax_lines_purchase = tax_line_ids.filtered(lambda x: x.debit)
        tax_sales = sum(tax_lines_sale.mapped("credit"))
        tax_purchase = sum(tax_lines_purchase.mapped("debit"))

        tax_balance = tax_sales - tax_purchase

        last_apuramento_id = self.env["apuramento.iva"].search(
            [("line_ids", "!=", False)], limit=1
        )
        previous_to_report = (
            last_apuramento_id.line_ids[0].amount_to_report if last_apuramento_id else 0
        )

        new_balance = tax_balance - previous_to_report

        move_line_vals = []

        if previous_to_report > 0:
            move_line_vals += self.get_move_line_vals(
                debit_account_code=IVA_APURAMENTO_ACC,
                credit_account_code=IVA_TO_REVOCER_ACC,
                amount=previous_to_report,
                reverse_lines=True,
            )

        if tax_sales > 0:
            move_line_vals += self.get_move_line_vals(
                debit_account_code=IVA_SALE_ACC,
                credit_account_code=IVA_APURAMENTO_ACC,
                amount=tax_sales,
            )

        if tax_purchase > 0:
            move_line_vals += self.get_move_line_vals(
                debit_account_code=IVA_APURAMENTO_ACC,
                credit_account_code=IVA_PURCHASE_ACC,
                amount=tax_purchase,
                reverse_lines=True,
            )

        if new_balance > 0:
            move_line_vals += self.get_move_line_vals(
                debit_account_code=IVA_APURAMENTO_ACC,
                credit_account_code=IVA_TO_PAY_ACC,
                amount=new_balance,
            )

        if new_balance < 0:
            move_line_vals += self.get_move_line_vals(
                debit_account_code=IVA_TO_REVOCER_ACC,
                credit_account_code=IVA_APURAMENTO_ACC,
                amount=new_balance,
                reverse_lines=True,
            )

        apuramento_move_id = self.env["account.move"].create(
            {
                "date": self.date_end,
                "journal_id": self.journal_id.id,
                "line_ids": move_line_vals,
            }
        )

        if new_balance < 0:
            amount_to_report = 0
            amount_to_pay = 0
            amount_to_recover = abs(new_balance)
        else:
            amount_to_report = 0
            amount_to_recover = 0
            amount_to_pay = new_balance
        self.write(
            {
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.name,
                            "journal_id": self.journal_id.id,
                            "move_id": apuramento_move_id.id,
                            "amount_to_pay": amount_to_pay,
                            "amount_to_recover": amount_to_recover,
                            "amount_to_report": amount_to_report,
                        },
                    )
                ]
            }
        )
        apuramento_move_id.action_post()

    def reimburse_iva(self):
        if not self.reimbursement_date:
            raise UserError("Favor preencher a 'Data de Reembolso' antes de solicitar!")
        for line in self.line_ids:
            if (
                not line.amount_to_recover
                or line.amount_to_report
                or line.amount_reimburse
            ):
                continue
            reimburse_move_id = line.move_id.copy({"date": self.reimbursement_date})
            move_lines = self.get_move_line_vals(
                debit_account_code=IVA_REIMBURSEMENT_ACC,
                credit_account_code=IVA_TO_REVOCER_ACC,
                amount=line.amount_to_recover,
                reverse_lines=True,
            )
            reimburse_move_id.write({"line_ids": move_lines})
            reimburse_move_id.action_post()
            line.write(
                {
                    "reimburse_move_id": reimburse_move_id.id,
                    "amount_reimburse": line.amount_to_recover,
                    "amount_to_recover": 0,
                }
            )

    def report_iva(self):
        for line in self.line_ids:
            if line.amount_to_recover and not (
                line.amount_to_report or line.amount_reimburse
            ):
                line.write(
                    {
                        "amount_to_report": line.amount_to_recover,
                        "amount_to_recover": 0,
                    }
                )

    def report_iva_overdue(self):
        for line in self.line_ids:
            if line.amount_to_recover and not (
                line.amount_to_report or line.amount_reimburse
            ):
                line.write(
                    {
                        "amount_to_report": line.amount_to_recover,
                        "amount_to_recover": 0,
                        "is_amount_to_report_overdue": True,
                    }
                )

    def action_reset_to_draft(self, unlink_moves=False):
        """
        Voltar este apuramento para rascunho:
        - Coloca os lançamentos (move_id e reimburse_move_id) em Draft
        - Remove reconciliações se houver
        - Limpa as linhas do apuramento para permitir gerar de novo
        """

        for rec in self:
            for line in rec.line_ids:
                for move in (line.reimburse_move_id, line.move_id):
                    if not move:
                        continue
                    if any(move.line_ids.mapped("reconciled")):
                        move.line_ids.remove_move_reconcile()
                    if move.state == "posted":
                        move.button_draft()
                    if unlink_moves:
                        move.unlink()
            rec.line_ids.unlink()
            rec.write({
                "reimbursement_date": False,
                "is_overdue": False,
            })


# TODO I don't think this model is necessary, it's for a One2Many but there's always
# only one object, so it should just be fields on the regular model
class ApuramentoIvaAccount(models.Model):
    _name = "apuramento.iva.line"
    _description = "Linha Apuramento Iva"

    name = fields.Char(string="Descrição")
    apuramento_iva_id = fields.Many2one(
        comodel_name="apuramento.iva", string="Apuramento Iva", ondelete="cascade"
    )
    year = fields.Integer(string="Ano", default=lambda self: fields.Date.today().year)
    currency_id = fields.Many2one(
        comodel_name="res.currency",
        string="Moeda",
        default=lambda self: self.env.company.currency_id.id,
    )
    journal_id = fields.Many2one(comodel_name="account.journal", string="Diário")
    move_id = fields.Many2one(
        comodel_name="account.move", string="Lançamento de Diário"
    )
    amount_to_pay = fields.Float(string="IVA Pagar")
    amount_to_report = fields.Float(string="IVA Reportar")
    amount_to_recover = fields.Float(string="IVA Recuperar")
    is_amount_to_report_overdue = fields.Boolean(string="IVA Reportar Fora do Prazo")
    amount_reimburse = fields.Float(string="IVA Reembolso")
    reimburse_move_id = fields.Many2one(
        comodel_name="account.move", string="Lançamento de Reembolso"
    )
