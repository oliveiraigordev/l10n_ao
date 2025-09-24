import datetime
from dateutil.relativedelta import relativedelta
import itertools
from odoo.exceptions import UserError
from odoo import api, fields, models, _


class ResCompanyRP(models.Model):
    _inherit = "res.company"

    cash_flow_in_payment = fields.Boolean('Registar Fluxo de Caixa no Pagamento')

    cash_flow_in_payment_register = fields.Boolean('Registar Fluxo de Caixa no Pagamento')

    def _get_and_update_tax_closing_moves(self, in_period_date, fiscal_positions=None, include_domestic=False):
        """ Searches for tax closing moves. If some are missing for the provided parameters,
        they are created in draft state. Also, existing moves get updated in case of configuration changes
        (closing journal or periodicity, for example). Note the content of these moves stays untouched.

        :param in_period_date: A date within the tax closing period we want the closing for.
        :param fiscal_positions: The fiscal positions we want to generate the closing for (as a recordset).
        :param include_domestic: Whether or not the domestic closing (i.e. the one without any fiscal_position_id) must be included

        :return: The closing moves, as a recordset.
        """
        self.ensure_one()

        if not fiscal_positions:
            fiscal_positions = []

        # Compute period dates depending on the date
        period_start, period_end = self._get_tax_closing_period_boundaries(in_period_date)
        activity_deadline = period_end + relativedelta(days=self.account_tax_periodicity_reminder_day)

        # Search for an existing tax closing move
        tax_closing_activity_type = self.env.ref('account_reports.tax_closing_activity_type', raise_if_not_found=False)
        tax_closing_activity_type_id = tax_closing_activity_type.id if tax_closing_activity_type else False

        all_closing_moves = self.env['account.move']
        for fpos in itertools.chain(fiscal_positions, [None] if include_domestic else []):

            tax_closing_move = self.env['account.move'].search([
                ('state', '=', 'draft'),
                ('company_id', '=', self.id),
                ('activity_ids.activity_type_id', '=', tax_closing_activity_type_id),
                ('tax_closing_end_date', '>=', period_start),
                ('fiscal_position_id', '=', fpos.id if fpos else None),
            ])

            # This should never happen, but can be caused by wrong manual operations
            if len(tax_closing_move) > 1:
                if fpos:
                    error = _(
                        "Multiple draft tax closing entries exist for fiscal position %s after %s. There should be at most one. \n %s")
                    params = (fpos.name, period_start, tax_closing_move.mapped('display_name'))

                else:
                    error = _(
                        "Multiple draft tax closing entries exist for your domestic region after %s. There should be at most one. \n %s")
                    params = (period_start, tax_closing_move.mapped('display_name'))

                raise UserError(error % params)

            # Compute tax closing description
            ref = self._get_tax_closing_move_description(self.account_tax_periodicity, period_start, period_end, fpos)

            # Values for update/creation of closing move
            closing_vals = {
                'journal_id': self.account_tax_periodicity_journal_id.id,
                'date': period_end,
                'tax_closing_end_date': period_end,
                'fiscal_position_id': fpos.id if fpos else None,
                'ref': ref,
                'name': '/',
                # Explicitly set a void name so that we don't set the sequence for the journal and don't consume a sequence number
            }

            if tax_closing_move:
                # Update the next activity on the existing move
                for act in tax_closing_move.activity_ids:
                    if act.activity_type_id.id == tax_closing_activity_type_id:
                        act.write({'date_deadline': activity_deadline})

                tax_closing_move.write(closing_vals)
            else:
                # Create a new, empty, tax closing move
                tax_closing_move = self.env['account.move'].create(closing_vals)

                group_account_manager = self.env.ref('account.group_account_manager')
                advisor_user = tax_closing_activity_type.default_user_id if tax_closing_activity_type else self.env[
                    'res.users']
                if advisor_user and not (
                        self in advisor_user.company_ids and group_account_manager in advisor_user.groups_id):
                    advisor_user = self.env['res.users']

                if not advisor_user:
                    advisor_user = self.env['res.users'].search(
                        [('company_ids', 'in', self.ids), ('groups_id', 'in', group_account_manager.ids)],
                        limit=1, order="id ASC")

                # self.env['mail.activity'].with_context(mail_activity_quick_update=True).create({
                #      'res_id': tax_closing_move.id if tax_closing_move else self.env.o.id,
                #      'res_model_id': self.env['ir.model']._get_id('account.move'),
                #      'activity_type_id': tax_closing_activity_type_id,
                #      'date_deadline': activity_deadline,
                #      'automated': True,
                #      'user_id': advisor_user.id or self.env.user.id
                #  })

            all_closing_moves += tax_closing_move if tax_closing_move else all_closing_moves

        return all_closing_moves
