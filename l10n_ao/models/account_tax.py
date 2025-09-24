import math
from odoo import fields, models, api, _, Command
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import formatLang
from odoo.tools import frozendict
from odoo.tools.float_utils import float_round
from .saft_ao_file import saft_clean_void_values
from odoo.exceptions import UserError
from odoo.exceptions import ValidationError
import re


class AccountTaxAng(models.Model):
    _inherit = "account.tax"


    tax_type = fields.Selection([('IVA', 'IVA'), ('NS', 'Não Sujeição'), ('IS', 'Imp do Selo')], string="SAFT Tax Type")
    tax_code = fields.Selection(string="SAFT Tax Code",
                                selection=[('RED', 'Reduzida'), ('NOR', 'Normal'), ('INT', 'Intermédia'),
                                           ('ISE', 'Isenta'), ('NS', 'Não Sujeição'), ('OUT', 'Outra')])
    wth_type = fields.Selection(string="Withholding Type",
                                selection=[('IRT', 'Imposto sobre o rendimento de trabalho'),
                                           ('II', 'Imposto Industrial'), ('IS', 'Imposto do Selo'),
                                           ('IVA', 'IVA Cativo'), ('IPU', 'Imposto predial urbano'),
                                           ('IAC', 'Imposto sobre a aplicação de capitais'),
                                           ('IAC', 'Imposto sobre a aplicação de capitais'),
                                           ('OU', 'Outros tipos de impostos retidos')],
                                required=False, default="II")
    is_withholding = fields.Boolean("Is Withholding")
    dont_affect_invoice = fields.Boolean("Don't Affect Invoice",
                                         help="""Mark if you don't want the tax amount to affect the invoice total amount""")

    limit_amount_wht = fields.Float(_("Limit Amount Wht"), default=0,
                                    help="Withholding Tax will be applied only if base amount more or equal to threshold amount")
    iva_tax_exemption_reason_id = fields.Many2one("tax.exemption.reason", string="IVA Tax Exemption Reason")
    hide_invoice = fields.Boolean("Hide in Invoice",
                                  help="""Check if you don't want to show this Tax in invoice report""")
    margin_affect = fields.Boolean(_("Affect Margin"))
    iva_tax_type = fields.Selection(string="Tipo de IVA",
                                    selection=[('DEDU', 'Dedutível'), ('NDEDU', 'Não dedutível'), ('SUP', 'Suportado'), ('CAT50', 'Cativo 50%'),
                                               ('CAT100', 'Cativo 100%'), ('AUTOLIQ', 'Autoliquidação'), ('LIQ', 'Liquidado'), ('IS', 'Isento')])

    def _compute_amount(self, base_amount, price_unit, quantity=1.0, product=None, partner=None, fixed_multiplicator=1,
                        invoice_lines=None):

        """ Returns the amount of a single tax. base_amount is the actual amount on which the tax is applied, which is
            price_unit * quantity eventually affected by previous taxes (if tax is include_base_amount XOR price_include)
        """
        self.ensure_one()

        # Verificar se o valor do artigo é inferior ou igual a 20.000
        if base_amount <= 20000 and invoice_lines:
            # Somar o valor total dos serviços
            total_servicos = sum(line['base_amount'] for line in invoice_lines if line['product'].type == 'service')
            base_amount = total_servicos

        if self.is_withholding and self.limit_amount_wht > 0 and base_amount < self.limit_amount_wht:
            return 0

        if self.amount_type == 'fixed':
            if base_amount:
                return math.copysign(quantity, base_amount) * self.amount
            else:
                return quantity * self.amount

        price_include = self._context.get('force_price_include', self.price_include)

        if self.amount_type == 'percent' and not price_include:
            return base_amount * self.amount / 100

        if self.amount_type == 'percent' and price_include:
            return base_amount - (base_amount / (1 + self.amount / 100))

        if self.amount_type == 'division' and not price_include:
            return base_amount / (1 - self.amount / 100) - base_amount if (1 - self.amount / 100) else 0.0

        if self.amount_type == 'division' and price_include:
            return base_amount - (base_amount * (self.amount / 100))


    @api.model
    def _compute_taxes_for_single_line(self, base_line, handle_price_include=True, include_caba_tags=False,
                                       early_pay_discount_computation=None, early_pay_discount_percentage=None):
        # Adicionou-se esta linha para que caso exista margem na linha se possa fazer o calculo correcto do amount_total.
        record = base_line.get("record", None)
        if self.env.company.country_id.code == 'AO' and record:
            margin_value = 0.0
            orig_price_unit_after_discount = 0.0
            if base_line['record'] != None:
                if isinstance(base_line['record'], dict):
                    margin_value = base_line['record'].get('margin_value', 0)
                elif hasattr(base_line['record'], 'margin_value'):
                    margin_value = getattr(base_line['record'], 'margin_value', 0)
                if margin_value > 0:
                    tax = base_line['taxes'].filtered(
                        lambda r: not r.tax_exigibility == 'on_payment' and r.margin_affect)
                    if tax:
                        margin_value = base_line['price_unit'] * (base_line['record']['margin_value'] / 100)
                        margin_value = margin_value + (margin_value * (tax.amount / 100))
                    else:
                        margin_value = base_line['price_unit'] * (base_line['record']['margin_value'] / 100)
                orig_price_unit_after_discount = (base_line['price_unit'] + margin_value) * (
                        1 - (base_line['discount'] / 100.0))
            price_unit_after_discount = orig_price_unit_after_discount
            taxes = base_line['taxes']._origin
            currency = base_line['currency'] or self.env.company.currency_id
            rate = base_line['rate']

            if early_pay_discount_computation in ('included', 'excluded'):
                remaining_part_to_consider = (100 - early_pay_discount_percentage) / 100.0
                price_unit_after_discount = remaining_part_to_consider * price_unit_after_discount

            if taxes:

                if handle_price_include is None:
                    manage_price_include = bool(base_line['handle_price_include'])
                else:
                    manage_price_include = handle_price_include

                taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                    price_unit_after_discount,
                    currency=currency,
                    quantity=base_line['quantity'],
                    product=base_line['product'],
                    partner=base_line['partner'],
                    is_refund=base_line['is_refund'],
                    handle_price_include=manage_price_include,
                    include_caba_tags=include_caba_tags,
                )

                to_update_vals = {
                    'tax_tag_ids': [Command.set(taxes_res['base_tags'])],
                    'price_subtotal': taxes_res['total_excluded'],
                    'price_total': taxes_res['total_included'],
                }

                if early_pay_discount_computation == 'excluded':
                    new_taxes_res = taxes.with_context(**base_line['extra_context']).compute_all(
                        orig_price_unit_after_discount,
                        currency=currency,
                        quantity=base_line['quantity'],
                        product=base_line['product'],
                        partner=base_line['partner'],
                        is_refund=base_line['is_refund'],
                        handle_price_include=manage_price_include,
                        include_caba_tags=include_caba_tags,
                    )
                    for tax_res, new_taxes_res in zip(taxes_res['taxes'], new_taxes_res['taxes']):
                        delta_tax = new_taxes_res['amount'] - tax_res['amount']
                        tax_res['amount'] += delta_tax
                        to_update_vals['price_total'] += delta_tax

                tax_values_list = []
                for tax_res in taxes_res['taxes']:
                    # FIXME: Look to this to see if will not affect other moves.
                    if self.company_id.country_id.code != "AO" and not tax_res['tax_exigibility'] == 'on_payment':
                        tax_amount = tax_res['amount'] / rate
                        if self.company_id.tax_calculation_rounding_method == 'round_per_line':
                            tax_amount = currency.round(tax_amount)
                        tax_rep = self.env['account.tax.repartition.line'].browse(tax_res['tax_repartition_line_id'])

                        tax_values_list.append({
                            **tax_res,
                            'tax_repartition_line': tax_rep,
                            'base_amount_currency': tax_res['base'],
                            'base_amount': currency.round(tax_res['base'] / rate),
                            'tax_amount_currency': tax_res['amount'],
                            'tax_amount': tax_amount,
                        })

            else:
                price_subtotal = currency.round(price_unit_after_discount * base_line['quantity'])
                to_update_vals = {
                    'tax_tag_ids': [Command.clear()],
                    'price_subtotal': price_subtotal,
                    'price_total': price_subtotal,
                }
                tax_values_list = []

            return to_update_vals, tax_values_list
        else:
            return super(AccountTaxAng, self)._compute_taxes_for_single_line(base_line, handle_price_include,
                                                                             include_caba_tags,
                                                                             early_pay_discount_computation,early_pay_discount_percentage)

    def compute_all(self, price_unit, currency=None, quantity=1.0, product=None, partner=None, is_refund=False,
                    handle_price_include=True, include_caba_tags=False, fixed_multiplicator=1, margin_value=None):
        """Compute all information required to apply taxes (in self + their children in case of a tax group).
        We consider the sequence of the parent for group of taxes.
            Eg. considering letters as taxes and alphabetic order as sequence :
            [G, B([A, D, F]), E, C] will be computed as [A, D, F, C, E, G]



        :param price_unit: The unit price of the line to compute taxes on.
        :param currency: The optional currency in which the price_unit is expressed.
        :param quantity: The optional quantity of the product to compute taxes on.
        :param product: The optional product to compute taxes on.
            Used to get the tags to apply on the lines.
        :param partner: The optional partner compute taxes on.
            Used to retrieve the lang to build strings and for potential extensions.
        :param is_refund: The optional boolean indicating if this is a refund.
        :param handle_price_include: Used when we need to ignore all tax included in price. If False, it means the
            amount passed to this method will be considered as the base of all computations.
        :param include_caba_tags: The optional boolean indicating if CABA tags need to be taken into account.
        :param fixed_multiplicator: The amount to multiply fixed amount taxes by.
        :return: {
            'total_excluded': 0.0,    # Total without taxes
            'total_included': 0.0,    # Total with taxes
            'total_void'    : 0.0,    # Total with those taxes, that don't have an account set
            'base_tags: : list<int>,  # Tags to apply on the base line
            'taxes': [{               # One dict for each tax in self and their children
                'id': int,
                'name': str,
                'amount': float,
                'base': float,
                'sequence': int,
                'account_id': int,
                'refund_account_id': int,
                'analytic': bool,
                'price_include': bool,
                'tax_exigibility': str,
                'tax_repartition_line_id': int,
                'group': recordset,
                'tag_ids': list<int>,
                'tax_ids': list<int>,
            }],
        } """
        if not self:
            company = self.env.company
        else:
            company = self[0].company_id

        # 1) Flatten the taxes.
        taxes, groups_map = self.flatten_taxes_hierarchy(create_map=True)

        # 2) Deal with the rounding methods
        if not currency:
            currency = company.currency_id

        # By default, for each tax, tax amount will first be computed
        # and rounded at the 'Account' decimal precision for each
        # PO/SO/invoice line and then these rounded amounts will be
        # summed, leading to the total amount for that tax. But, if the
        # company has tax_calculation_rounding_method = round_globally,
        # we still follow the same method, but we use a much larger
        # precision when we round the tax amount for each line (we use
        # the 'Account' decimal precision + 5), and that way it's like
        # rounding after the sum of the tax amounts of each line
        prec = currency.rounding

        # In some cases, it is necessary to force/prevent the rounding of the tax and the total
        # amounts. For example, in SO/PO line, we don't want to round the price unit at the
        # precision of the currency.
        # The context key 'round' allows to force the standard behavior.
        round_tax = False if company.tax_calculation_rounding_method == 'round_globally' else True
        if 'round' in self.env.context:
            round_tax = bool(self.env.context['round'])

        if not round_tax:
            prec *= 1e-5

        # 3) Iterate the taxes in the reversed sequence order to retrieve the initial base of the computation.
        #     tax  |  base  |  amount  |
        # /\ ----------------------------
        # || tax_1 |  XXXX  |          | <- we are looking for that, it's the total_excluded
        # || tax_2 |   ..   |          |
        # || tax_3 |   ..   |          |
        # ||  ...  |   ..   |    ..    |
        #    ----------------------------
        def recompute_base(base_amount, fixed_amount, percent_amount, division_amount):
            # Recompute the new base amount based on included fixed/percent amounts and the current base amount.
            # Example:
            #  tax  |  amount  |   type   |  price_include  |
            # -----------------------------------------------
            # tax_1 |   10%    | percent  |  t
            # tax_2 |   15     |   fix    |  t
            # tax_3 |   20%    | percent  |  t
            # tax_4 |   10%    | division |  t
            # -----------------------------------------------

            # if base_amount = 145, the new base is computed as:
            # (145 - 15) / (1.0 + 30%) * 90% = 130 / 1.3 * 90% = 90
            return (base_amount - fixed_amount) / (1.0 + percent_amount / 100.0) * (100 - division_amount) / 100

        # The first/last base must absolutely be rounded to work in round globally.
        # Indeed, the sum of all taxes ('taxes' key in the result dictionary) must be strictly equals to
        # 'price_included' - 'price_excluded' whatever the rounding method.
        #
        # Example using the global rounding without any decimals:
        # Suppose two invoice lines: 27000 and 10920, both having a 19% price included tax.
        #
        #                   Line 1                      Line 2
        # -----------------------------------------------------------------------
        # total_included:   27000                       10920
        # tax:              27000 / 1.19 = 4310.924     10920 / 1.19 = 1743.529
        # total_excluded:   22689.076                   9176.471
        #
        # If the rounding of the total_excluded isn't made at the end, it could lead to some rounding issues
        # when summing the tax amounts, e.g. on invoices.
        # In that case:
        #  - amount_untaxed will be 22689 + 9176 = 31865
        #  - amount_tax will be 4310.924 + 1743.529 = 6054.453 ~ 6054
        #  - amount_total will be 31865 + 6054 = 37919 != 37920 = 27000 + 10920
        #
        # By performing a rounding at the end to compute the price_excluded amount, the amount_tax will be strictly
        # equals to 'price_included' - 'price_excluded' after rounding and then:
        #   Line 1: sum(taxes) = 27000 - 22689 = 4311
        #   Line 2: sum(taxes) = 10920 - 2176 = 8744
        #   amount_tax = 4311 + 8744 = 13055
        #   amount_total = 31865 + 13055 = 37920

        base = currency.round(price_unit * quantity)

        # For the computation of move lines, we could have a negative base value.
        # In this case, compute all with positive values and negate them at the end.
        sign = 1
        if currency.is_zero(base):
            sign = -1 if fixed_multiplicator < 0 else 1
        elif base < 0:
            sign = -1
            base = -base

        # Store the totals to reach when using price_include taxes (only the last price included in row)
        total_included_checkpoints = {}
        i = len(taxes) - 1
        store_included_tax_total = True
        # Keep track of the accumulated included fixed/percent amount.
        incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
        # Store the tax amounts we compute while searching for the total_excluded
        cached_tax_amounts = {}
        if handle_price_include:
            for tax in reversed(taxes):
                tax_repartition_lines = (
                        is_refund
                        and tax.refund_repartition_line_ids
                        or tax.invoice_repartition_line_ids
                ).filtered(lambda x: x.repartition_type == "tax")
                sum_repartition_factor = sum(tax_repartition_lines.mapped("factor"))

                if tax.include_base_amount:
                    base = recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount)
                    incl_fixed_amount = incl_percent_amount = incl_division_amount = 0
                    store_included_tax_total = True
                if tax.price_include or self._context.get('force_price_include'):
                    if tax.amount_type == 'percent':
                        incl_percent_amount += tax.amount * sum_repartition_factor
                    elif tax.amount_type == 'division':
                        incl_division_amount += tax.amount * sum_repartition_factor
                    elif tax.amount_type == 'fixed':
                        incl_fixed_amount += abs(quantity) * tax.amount * sum_repartition_factor * abs(
                            fixed_multiplicator)
                    else:
                        # tax.amount_type == other (python)
                        tax_amount = tax._compute_amount(base, sign * price_unit, quantity, product, partner,
                                                         fixed_multiplicator) * sum_repartition_factor
                        incl_fixed_amount += tax_amount
                        # Avoid unecessary re-computation
                        cached_tax_amounts[i] = tax_amount
                    # In case of a zero tax, do not store the base amount since the tax amount will
                    # be zero anyway. Group and Python taxes have an amount of zero, so do not take
                    # them into account.
                    if store_included_tax_total and (
                            tax.amount or tax.amount_type not in ("percent", "division", "fixed")
                    ):
                        total_included_checkpoints[i] = base
                        store_included_tax_total = False
                i -= 1

        total_excluded = currency.round(
            recompute_base(base, incl_fixed_amount, incl_percent_amount, incl_division_amount))

        # 4) Iterate the taxes in the sequence order to compute missing tax amounts.
        # Start the computation of accumulated amounts at the total_excluded value.
        base = total_included = total_void = total_excluded

        # Flag indicating the checkpoint used in price_include to avoid rounding issue must be skipped since the base
        # amount has changed because we are currently mixing price-included and price-excluded include_base_amount
        # taxes.
        skip_checkpoint = False

        # Get product tags, account.account.tag objects that need to be injected in all
        # the tax_tag_ids of all the move lines created by the compute all for this product.
        product_tag_ids = product.account_tag_ids.ids if product else []

        taxes_vals = []
        i = 0
        cumulated_tax_included_amount = 0
        for tax in taxes:
            price_include = self._context.get('force_price_include', tax.price_include)

            if price_include or tax.is_base_affected:
                tax_base_amount = base
            else:
                tax_base_amount = total_excluded

            tax_repartition_lines = (
                    is_refund and tax.refund_repartition_line_ids or tax.invoice_repartition_line_ids).filtered(
                lambda x: x.repartition_type == 'tax')
            sum_repartition_factor = sum(tax_repartition_lines.mapped('factor'))

            # compute the tax_amount
            if not skip_checkpoint and price_include and total_included_checkpoints.get(
                    i) is not None and sum_repartition_factor != 0:
                # We know the total to reach for that tax, so we make a substraction to avoid any rounding issues
                tax_amount = total_included_checkpoints[i] - (base + cumulated_tax_included_amount)
                cumulated_tax_included_amount = 0
            else:
                tax_amount = tax.with_context(force_price_include=False)._compute_amount(
                    tax_base_amount, sign * price_unit, quantity, product, partner, fixed_multiplicator)

            # L10N_AO mapear apenas o total quando o imposto não for cativo
            tax_amount = float_round(tax_amount, precision_rounding=prec)
            factorized_tax_amount = float_round(tax_amount * sum_repartition_factor, precision_rounding=prec)

            # L10N_AO TIS: Added to not include the amount in the total amount
            if (tax.dont_affect_invoice and self.env.context.get("default_move_type") in \
                ('out_invoice', 'in_invoice', 'out_refund',
                 'in_refund') and tax.company_id.country_id.code != "AO") or (
                    self.env.context.get("payment_with_withholding") == 'not_with' and tax.dont_affect_invoice):
                tax_amount = 0
                factorized_tax_amount = 0

            if price_include and total_included_checkpoints.get(i) is None:
                cumulated_tax_included_amount += factorized_tax_amount

            # If the tax affects the base of subsequent taxes, its tax move lines must
            # receive the base tags and tag_ids of these taxes, so that the tax report computes
            # the right total
            subsequent_taxes = self.env['account.tax']
            subsequent_tags = self.env['account.account.tag']
            if tax.include_base_amount:
                subsequent_taxes = taxes[i + 1:].filtered('is_base_affected')

                taxes_for_subsequent_tags = subsequent_taxes

                if not include_caba_tags:
                    taxes_for_subsequent_tags = subsequent_taxes.filtered(lambda x: x.tax_exigibility != 'on_payment')

                subsequent_tags = taxes_for_subsequent_tags.get_tax_tags(is_refund, 'base')

            # Compute the tax line amounts by multiplying each factor with the tax amount.
            # Then, spread the tax rounding to ensure the consistency of each line independently with the factorized
            # amount. E.g:
            #
            # Suppose a tax having 4 x 50% repartition line applied on a tax amount of 0.03 with 2 decimal places.
            # The factorized_tax_amount will be 0.06 (200% x 0.03). However, each line taken independently will compute
            # 50% * 0.03 = 0.01 with rounding. It means there is 0.06 - 0.04 = 0.02 as total_rounding_error to dispatch
            # in lines as 2 x 0.01.
            repartition_line_amounts = [float_round(tax_amount * line.factor, precision_rounding=prec) for line in
                                        tax_repartition_lines]
            total_rounding_error = float_round(factorized_tax_amount - sum(repartition_line_amounts),
                                               precision_rounding=prec)
            nber_rounding_steps = int(abs(total_rounding_error / currency.rounding))
            rounding_error = float_round(nber_rounding_steps and total_rounding_error / nber_rounding_steps or 0.0,
                                         precision_rounding=prec)

            for repartition_line, line_amount in zip(tax_repartition_lines, repartition_line_amounts):

                if nber_rounding_steps:
                    line_amount += rounding_error
                    nber_rounding_steps -= 1

                if not include_caba_tags and tax.tax_exigibility == 'on_payment':
                    repartition_line_tags = self.env['account.account.tag']
                else:
                    repartition_line_tags = repartition_line.tag_ids
                # TIS: VALIDAR SE O IMPOSTO É DO TIPO RETENÇÃO CASO SEJA
                if not (tax.dont_affect_invoice or tax.margin_affect) and (self.env.context.get("default_move_type") in \
                                                                           ('out_invoice', 'in_invoice', 'out_refund',
                                                                            'in_refund') or not self.env.context.get(
                            "default_move_type")) or \
                        tax.is_withholding and self.env.context.get('on_payment') and self.env.context.get(
                    'payment_with_withholding') == 'with':
                    taxes_vals.append({
                        'id': tax.id,
                        'name': partner and tax.with_context(lang=partner.lang).name or tax.name,
                        'amount': sign * line_amount,
                        'base': float_round(sign * tax_base_amount, precision_rounding=prec),
                        'sequence': tax.sequence,
                        'account_id': repartition_line._get_aml_target_tax_account().id,
                        'analytic': tax.analytic,
                        'use_in_tax_closing': repartition_line.use_in_tax_closing,
                        'price_include': price_include,
                        'tax_exigibility': tax.tax_exigibility,
                        'tax_repartition_line_id': repartition_line.id,
                        'group': groups_map.get(tax),
                        'tag_ids': (repartition_line_tags + subsequent_tags).ids + product_tag_ids,
                        'tax_ids': subsequent_taxes.ids,
                    })

                if not repartition_line.account_id:
                    total_void += line_amount

            # Affect subsequent taxes
            if tax.include_base_amount:
                base += factorized_tax_amount
                if not price_include:
                    skip_checkpoint = True

            total_included += factorized_tax_amount
            i += 1

        base_taxes_for_tags = taxes
        if not include_caba_tags:
            base_taxes_for_tags = base_taxes_for_tags.filtered(lambda x: x.tax_exigibility != 'on_payment')

        base_rep_lines = base_taxes_for_tags.mapped(
            is_refund and 'refund_repartition_line_ids' or 'invoice_repartition_line_ids').filtered(
            lambda x: x.repartition_type == 'base')

        return {
            'base_tags': base_rep_lines.tag_ids.ids + product_tag_ids,
            'taxes': taxes_vals,
            'total_excluded': sign * total_excluded,
            'total_included': sign * currency.round(total_included),
            'total_void': sign * currency.round(total_void),
        }

    @api.onchange("iva_tax_exemption_reason_id", "amount")
    def onchange_tax_exemption(self):
        for tax in self:
            if tax.tax_code == "ISE":
                tax.description = tax.iva_tax_exemption_reason_id.code

    def get_saft_data(self):

        # tax_table = {}
        result = {
            'TaxTable': {
                'TaxTableEntry': [],
            }
        }

        for tax in self:
            tax_table = {
                'TaxType': tax.tax_type,
                'TaxCountryRegion': 'AO',
                'TaxCode': tax.tax_code,
                'Description': tax.name,
            }
            if tax.amount_type in ["percent",
                                   "division"]:  # TODO: REVISAR SE O REGIME APENAS PEDE ESTES TIPOS DE IMPOSTOS
                tax_table['TaxPercentage'] = str(format(tax.amount, '.2f'))
            elif tax.amount_type in ['fixed']:
                tax_table['TaxAmount'] = str(format(tax.amount, '.2f'))

            # if tax.expiration_date:
            #     tax_table['TaxExpirationDate'] = "",tax.expiration_date
            result['TaxTable']['TaxTableEntry'].append(tax_table)

        return result


class AccountTaxTemplateAng(models.Model):
    _inherit = "account.tax.template"

    country_id = fields.Many2one(string="Country", comodel_name='res.country', required=True,
                                 help="The country for which this tax is applicable.")
    tax_type = fields.Selection([('IVA', 'IVA'), ('NS', 'Não Sujeição'), ('IS', 'Imp do Selo')], string="SAFT Tax Type")
    tax_code = fields.Selection(string="SAFT Tax Code",
                                selection=[('RED', 'Reduzida'), ('NOR', 'Normal'), ('INT', 'Intermédia'),
                                           ('ISE', 'Isenta'), ('NS', 'Não Sujeição'), ('OUT', 'Outra')])
    wth_type = fields.Selection(string="Withholding Type",
                                selection=[('IRT', 'Imposto sobre o rendimento de trabalho'),
                                           ('II', 'Imposto Industrial'), ("IS", "Imposto do Selo"),
                                           ("IVA", "IVA Cativo"), ("IPU", "Imposto predial urbano")],
                                required=False, default="II", )
    is_withholding = fields.Boolean("Is Withholding")
    dont_affect_invoice = fields.Boolean("Don't Affect Invoice",
                                         help="""Mark if you don't want the tax amount to affect the invoice total amount""")
    limit_amount_wht = fields.Float(_("Limit Amount Wht"), default=0,
                                    help="Withholding Tax will be applied only if base amount more or equal to threshold amount")
    iva_tax_exemption_reason_id = fields.Many2one("tax.exemption.reason", string="IVA Tax Exemption Reason")
    hide_invoice = fields.Boolean("Hide in Invoice",
                                  help="""Check if you don't want to show this Tax in invoice report""")

    # Override method to add our own fields.
    def _get_tax_vals(self, company, tax_template_to_tax):
        """ This method generates a dictionary of all the values for the tax that will be created.
        """
        # Compute children tax ids
        children_ids = []
        for child_tax in self.children_tax_ids:
            if tax_template_to_tax.get(child_tax.id):
                children_ids.append(tax_template_to_tax[child_tax.id])

        self.ensure_one()
        val = {
            'name': self.name,
            'type_tax_use': self.type_tax_use,
            'amount_type': self.amount_type,
            'active': self.active,
            'company_id': company.id,
            'sequence': self.sequence,
            'amount': self.amount,
            'description': self.description,
            'price_include': self.price_include,
            'include_base_amount': self.include_base_amount,
            # 'country_code': self.country_code,
            'tax_code': self.tax_code,
            'tax_type': self.tax_type,
            'wth_type': self.wth_type,
            'analytic': self.analytic,
            'tax_exigibility': self.tax_exigibility,
            'limit_amount_wht': self.limit_amount_wht,
            'is_withholding': self.is_withholding,
            'dont_affect_invoice': self.dont_affect_invoice,
            'hide_invoice': self.hide_invoice,
            # 'tax_regime_ids': self.tax_regime_ids, TODO: FAZER REVISÃO DO CÓDIGO PARA DEPOIS MAPEAR SO IMPOSTOS QUE SEJAM DO REGIME DE IVA DO CLIENTE
            'tax_scope': self.tax_scope,
            'tax_group_id': self.tax_group_id,
            # 'tag_ids': [(6, 0, [t.id for t in self.tag_ids])],
        }

        # We add repartition lines if there are some, so that if there are none,
        # default_get is called and creates the default ones properly.
        if self.invoice_repartition_line_ids:
            val['invoice_repartition_line_ids'] = self.invoice_repartition_line_ids.get_repartition_line_create_vals(
                company)
        if self.refund_repartition_line_ids:
            val['refund_repartition_line_ids'] = self.refund_repartition_line_ids.get_repartition_line_create_vals(
                company)

        if self.tax_group_id:
            val['tax_group_id'] = self.tax_group_id.id
        return val
