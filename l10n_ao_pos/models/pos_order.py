from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from odoo.addons.l10n_ao.sign import sign
import datetime
import logging
from odoo.addons.l10n_ao.models.saft_ao_file import saft_clean_void_values

_logger = logging.getLogger(__name__)


class PosOrderAng(models.Model):
    _inherit = "pos.order"
    _order = "system_entry_date desc"

    hash = fields.Char(string="Hash", copy=False, readonly=True, store=True)
    hash_control = fields.Char(string="Hash Control")
    content_to_sign = fields.Char("Content To Sign", readonly=True, store=True)
    pos_number = fields.Char("Number")
    system_entry_date = fields.Datetime("Data da Assinatura", copy=False)
    document_type = fields.Selection([('FR', 'Factura Recibo'), ('NC', 'Nota de Crédito')])
    saft_status_date = fields.Datetime("Saft Status Date", copy=False)

    def get_new_content_to_sign(self):
        if self.sequence_number - 1 >= 1:
            last_order = self.env['pos.order'].search(
                [('state', 'in', ['paid', 'done']), ('id', "!=", self.id),
                 ('company_id', '=', self.company_id.id),
                 ('system_entry_date', '<=', self.system_entry_date),
                 ('sequence_number', '=', self.sequence_number - 1)
                 ],
                order="system_entry_date desc", limit=1)

            last_order_hash = ""
            if last_order and last_order.hash:
                last_order_hash = last_order.hash
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='seconds') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='seconds')
            res = ";".join((fields.Date.to_string(self.date_order), system_entry_date,
                            self.pos_number,
                            format(float(self.amount_total), '.2f') if self.amount_total > 0 else format(
                                float(abs(self.amount_total)), '.2f'), last_order_hash))

        elif self.sequence_number - 1 == 0:
            system_entry_date = self.system_entry_date.isoformat(sep='T',
                                                                 timespec='seconds') if self.system_entry_date else fields.Datetime.now().isoformat(
                sep='T', timespec='seconds')
            res = ";".join((fields.Date.to_string(self.date_order), system_entry_date, self.pos_number,
                            format(float(self.amount_total), '.2f') if self.amount_total > 0 else format(
                                float(abs(self.amount_total)), '.2f'), ""))

        return res

    def sign_pos_order(self, content_data):
        response = sign.sign_content(content_data)
        if response:
            return response
        return content_data

    def write(self, vals):
        # if self.env.user.company_id.chart_template_id == self.env.ref('l10n_ao.ao_chart_template'):
        # has_been_posted = False
        for order in self:
            if vals.get('state') and vals['state'] in ['paid', 'done']:

                vals['system_entry_date'] = fields.Datetime.now()
                vals['saft_status_date'] = fields.Datetime.now()

                # pos_number = 0
                # sequence_number = 0
                if order.amount_total < 0 and not order.hash:
                    sequence = self.env['ir.sequence'].with_company(self.company_id).search(
                        []).next_by_code("l10n_ao_pos_refund")
                    vals['pos_number'] = f'{sequence}'
                    vals['sequence_number'] = sequence.split("/")[1]
                    vals['document_type'] = 'NC'
                elif order.amount_total >= 0 and not order.hash:
                    sequence = self.env['ir.sequence'].with_company(self.company_id).search([]).next_by_code(
                        "l10n_ao_pos")
                    vals['pos_number'] = f'{sequence}'
                    vals['sequence_number'] = sequence.split("/")[1]
                    vals['document_type'] = 'FR'
                orders = super(PosOrderAng, self).write(vals)
                content_hash = order.get_new_content_to_sign()
                content_signed = order.sign_pos_order(content_hash).split(";")
                vals['content_to_sign'] = content_signed
                if content_hash != content_signed:
                    vals['hash_control'] = content_signed[1] if len(content_signed) > 1 else "0"
                    vals['hash'] = content_signed[0]
        return super(PosOrderAng, self).write(vals)

    def get_saft_data(self):
        """
        Returns a list of invoices dictionaries in saft format fields
        :return:
        """
        total_debit = []
        total_credit = []
        result = {
            "SalesInvoices": {
                "NumberOfEntries": 0,
                "TotalDebit": 0,
                "TotalCredit": 0,
                "Invoice": [],
            },
        }
        # iva_exemption = self.env.ref("l10n_ao.%s_account_tax_iva_sales_isento_14" % self.env.company.id)
        pos_orders = self.filtered(
            lambda r: r.state in ['paid', 'done'] and r.company_id.id == self.env.company.id)
        bug_values = {
            'invoice_no_Tax': [],
            'line_void_product_id': [],
            'empty_exemption_reason': [],
        }

        for pos in pos_orders:
            if not any(line.tax_ids.filtered(
                    lambda r: (r.tax_code in ['NOR', 'ISE', 'RED', 'OUT', 'INT'] and r.tax_type in ['IVA']) or
                              (
                                      r.tax_code == 'NS' and r.tax_type == 'NS') and pos.company_id.id == self.env.company.id)
                       for line in
                       pos.lines):
                bug_values['invoice_no_Tax'].append(str(pos.pos_number))
            lines = pos.mapped('lines')
            for line in lines:
                if line.tax_ids.filtered(lambda r: r.amount == 0) and not \
                        line.tax_ids.filtered(lambda r: r.amount == 0)[0].iva_tax_exemption_reason_id.name:
                    bug_values['empty_exemption_reason'].append(pos.pos_number)
                if not line.product_id:
                    bug_values['line_void_product_id'].append(pos.pos_number)

        bug_values['invoice_no_Tax'] = list(set(bug_values['invoice_no_Tax']))
        bug_values['empty_exemption_reason'] = list((bug_values['empty_exemption_reason']))
        bug_values['line_void_product_id'] = list(dict.fromkeys(bug_values['line_void_product_id']))
        errors = {"1": "", "2": "", "3": ""}
        if bug_values:
            if bug_values.get('invoice_no_Tax'):
                msg = "it's not possible to generate SAFT file because the following invoices don't have taxes:\n %s" % (
                        str(bug_values['invoice_no_Tax']) + "\n")
                errors["1"] = msg
            elif bug_values.get('empty_exemption_reason'):
                msg = "It is not possible to generate a SAFT file because the invoices that follow have iva exemption but the motive was not added, please add:\n %s" % (
                        str(bug_values['empty_exemption_reason']) + "\n")
                errors["2"] = msg
            elif bug_values.get('line_void_product_id'):
                msg = "The lines in these invoices do not have products inserted, you must add the corresponding products for each line that is missing:\n %s" % (
                        str(bug_values['line_void_product_id']) + "\n")
                errors["3"] = msg
            if any(errors.values()):
                raise ValidationError([str(v) + "\n" for v in errors.values()])
        total_cancelled_invoice = 0

        for pos in pos_orders:
            status_code = 'N'
            # inv_refunds = pos.invoice_id.refund_invoice_ids.filtered(lambda r: r.state == 'paid')
            # refund_amount_total = sum(inv_refunds.mapped("amount_untaxed"))
            # if pos.state == 'paid' and abs(refund_amount_total) == abs(inv.amount_untaxed):
            #     status_code = 'A'
            #     total_cancelled_invoice += refund_amount_total
            # elif inv.state == 'paid' and not abs(refund_amount_total):
            #     status_code = 'F',
            #     total_cancelled_invoice += inv.amount_untaxed

            # if pos.invoice_id.journal_id.self_billing is True:
            #     status_code = 'S'
            # TODO: que caso são os documentos produzidos noutra aplicação.
            source_billing = "P"

            invoice_customer = {
                "InvoiceNo": pos.pos_number.replace(" ", " "),
                "DocumentStatus": {
                    "InvoiceStatus": status_code,
                    "InvoiceStatusDate": fields.Datetime.to_string(pos.account_move.saft_status_date)[
                                         0:10] + "T" + fields.Datetime.to_string(pos.account_move.saft_status_date)[
                                                       11:20] if
                    pos.account_move.saft_status_date else fields.Datetime.to_string(pos.date_order)[
                                                           0:10] + "T" + fields.Datetime.to_string(pos.date_order)[
                                                                         11:20],
                    "Reason": str(pos.name)[0:48] if pos.name else "",
                    "SourceID": pos.user_id.id,
                    "SourceBilling": source_billing,
                },
                "Hash": pos.hash if pos.hash else "",
                "HashControl": pos.hash_control if pos.hash_control else "0",
                "Period": int(fields.Date.to_string(pos.date_order)[5:7]),
                "InvoiceDate": fields.Date.to_string(pos.date_order),
                "InvoiceType": pos.document_type,
                "SpecialRegimes": {
                    "SelfBillingIndicator": "1" if pos.account_move.journal_id.auto_invoicing else "0",
                    "CashVATSchemeIndicator": "1" if pos.company_id.tax_exigibility else "0",
                    "ThirdPartiesBillingIndicator": "0",
                },
                "SourceID": pos.user_id.id,
                "EACCode": "",
                "SystemEntryDate": fields.Datetime.to_string(
                    pos.system_entry_date)[0:10] + "T" + fields.Datetime.to_string(pos.system_entry_date)[
                                                         11:20] if pos.system_entry_date else
                fields.Datetime.to_string(pos.date_order)[0:10] + "T" + fields.Datetime.to_string(pos.date_order)[
                                                                        11:20],
                "TransactionID": fields.Date.to_string(pos.account_move.date) + " " + str(pos.account_move.id).replace(
                    " ",
                    "") + " " + str(
                    pos.account_move.id) if pos.account_move else "",
                "CustomerID": pos.partner_id.id if (
                        pos.partner_id.vat and '999999999' not in pos.partner_id.vat) else '01',
                "ShipTo": "",  # TODO: 4.1.4.15,
                "ShipFrom": "",  # TODO: 4.1.4.16,
                "MovementEndTime": "",  # TODO: 4.1.4.17,
                "MovementStartTime": "",  # TODO: 4.1.4.18,
                "Line": [{
                    "LineNumber": line.id,
                    "OrderReferences": {
                        "OriginatingON": pos.note if pos.note else "",  # TODO:4.1.4.19.2.,
                        "OrderDate": "",
                    },
                    "ProductCode": line.product_id.id if line.product_id else line.id,
                    "ProductDescription": str(line.name)[0:199] if line.name else line.product_id.name[0:199],
                    "Quantity": line.qty if line.qty > 0 else line.qty * (-1) if line.qty < 0 else "0.00",
                    "UnitOfMeasure": line.product_id.uom_id.name,
                    "UnitPrice": format(line.price_unit * (1 - (line.discount or 0.0) / 100.0), '.4f'),
                    "TaxBase": "",
                    "TaxPointDate": datetime.datetime.strftime(pos.date_order, "%Y-%m-%d"),
                    # "References": {
                    #     "Reference": pos.pos_reference,
                    #     "Reason": str(pos.name)[0:48] if pos.name else "",
                    # },
                    "Description": line.name[0:199],
                    "ProductSerialNumber": {
                        "SerialNumber": line.product_id.default_code if line.product_id.default_code else "Desconhecido",
                        # TODO: 4.1.4.19.12.
                    },
                    "CreditAmount" if pos.document_type == "FR" else "DebitAmount": str(
                        format(abs(line.price_subtotal), '.2f')),
                    "Tax": [{
                        "TaxType": tax.tax_type,
                        "TaxCountryRegion": tax.country_id.code if tax.country_id else "AO",  # FIXME: 4.1.4.19.15.2.
                        "TaxCode": tax.tax_code,
                        "TaxAmount" if tax.amount_type in ["fixed"] else "TaxPercentage": str(
                            format(tax.amount, '.2f')),
                    } for tax in line.tax_ids if tax.tax_exigibility == "on_invoice"],
                    "TaxExemptionReason": line.tax_ids.filtered(lambda r: r.amount == 0)[
                                              0].iva_tax_exemption_reason_id.name[
                                          0:59] if line.tax_ids.filtered(
                        lambda
                            r: r.amount == 0) else "",
                    "TaxExemptionCode": line.tax_ids.filtered(lambda r: r.amount == 0)[
                        0].iva_tax_exemption_reason_id.code if line.tax_ids.filtered(
                        lambda
                            r: r.amount == 0) else "",
                    "SettlementAmount": line.discount,
                    "CustomsInformation": {  # TODO: 4.1.4.19.19.
                        "ARCNo": "",
                        "IECAmount": "",
                    },
                } for line in pos.lines],
                "DocumentTotals": {
                    "TaxPayable": format(pos.amount_tax, '.2f') if pos.amount_tax > 0 else format(pos.amount_tax * (-1),
                                                                                                  '.2f') if pos.amount_tax < 0 else "0.00",
                    "NetTotal": format(float(pos.amount_total - pos.amount_tax),
                                       '.2f') if pos.amount_total > 0 else format(
                        float((pos.amount_total * (-1)) - (pos.amount_tax * (-1))), '.2f') or "0.00",
                    # TODO: we must review this with invoice in different currency
                    "GrossTotal": format(float(pos.amount_total), '.2f') if pos.amount_total > 0 else format(
                        float(abs(pos.amount_total)), '.2f'),
                    # TODO: we must review this with invoice in different currency
                    "Currency": {
                        "CurrencyCode": pos.company_id.currency_id.name if pos.company_id.currency_id.name else "A0A",
                        "CurrencyAmount": pos.amount_total if pos.amount_total > 0 else pos.amount_total * (-1),
                        "ExchangeRate": round(
                            pos.company_id.currency_id._get_conversion_rate(pos.company_id.currency_id,
                                                                            pos.company_id.currency_id,
                                                                            pos.company_id, pos.date_order), 2),
                    } if pos.company_id.currency_id.name != 'AOA' else "",
                    "Settlement": {
                        "SettlementDiscount": "",
                        "SettlementAmount": "",
                        "SettlementDate": "",
                        "PaymentTerms": "",
                    },
                    "Payment": [{
                        "PaymentMechanism": "OU",
                        "PaymentAmount": format(pos.amount_total, '.2f') if pos.amount_total > 0 else format(
                            pos.amount_total * (-1), '.2f'),
                        "PaymentDate": datetime.datetime.strftime(pos.date_order, "%Y-%m-%d"),
                    }]

                },
                "WithholdingTax": [{
                    "WithholdingTaxType": tax.saft_wth_type,
                    "WithholdingTaxDescription": tax.name,
                    "WithholdingTaxAmount": tax.amount,  # round(tax.amount * ((tax.captive_percentage or 100) / 100),
                    #                               pos.company_id.currency_id.name),
                } for tax in pos.lines.mapped("tax_ids").filtered(lambda r: r.is_withholding)],
            }

            invoice_customer = saft_clean_void_values("", invoice_customer)
            result["SalesInvoices"]["Invoice"].append(invoice_customer)

            # total_debit.append(int(line.price_subtotal) * (-1)) pos if int(line.amount_tota
        total_debit = round(
            sum(abs(pos.amount_total) - abs(pos.amount_tax) for pos in pos_orders if pos.amount_total < 0), 2)
        total_credit = round(sum(pos.amount_total - pos.amount_tax for pos in pos_orders if pos.amount_total > 0), 2)
        result["SalesInvoices"]["TotalDebit"] = round(total_debit, 2)
        result["SalesInvoices"]["TotalCredit"] = round(total_credit, 2)

        result["SalesInvoices"]["NumberOfEntries"] = len(pos_orders)
        return result


class PosOrderAoLine(models.Model):
    _inherit = "pos.order.line"

    @api.constrains('price_unit')
    def _check_negative_value(self):
        for line in self:
            if self.env.user.company_id.country_id.code == 'AO':
                if line.price_unit < 0:
                    raise ValidationError(_("O preço unitário deve ser sempre positivo"))

    @api.constrains('product_id')
    def _check_vat(self):
        for line in self:
            if (line.product_id.taxes_id and not line.product_id.taxes_id.filtered(
                    lambda r: r.tax_type in ['IVA', 'NS'] and r.tax_code in ['NS', 'ISE',
                                                                             'NOR'])) or not line.product_id.taxes_id:
                raise ValidationError(
                    _("O produtos devem incluir imposto do tipo IVA, verifique porfavor se existe o importo IVA em todos os produtos que pretende facturar."))
