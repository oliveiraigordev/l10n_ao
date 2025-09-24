from odoo import fields, models, api, _
from odoo.exceptions import ValidationError
from .saft_ao_file import saft_clean_void_values


class ResPartnerAng(models.Model):
    _inherit = "res.partner"

    county_id = fields.Many2one("res.state.county", string="County")
    type_of_account = fields.Selection([('group', 'Grupo'), ('n_group', 'Não Grupo')], default="n_group",
                                       string="Tipo de Conta")
    supplier_immobilized = fields.Boolean("Imobilizado")
    type_of_immobilized = fields.Selection([('corp', 'Corpóreo'), ('incorp', 'Incorpóreo'), ('finan', 'Finaceiro')])
    is_supplier = fields.Boolean("É Fornecedor")
    sequence_code = fields.Integer("Código Interno")
    is_customer = fields.Boolean("É Cliente")

    #Campos para Ocultar o Iva a Cativar
    is_retaining_entity_50 = fields.Boolean(string="Entidade Cativadora 50%?")
    is_retaining_entity_100 = fields.Boolean(string="Entidade Cativadora 100%?")

    @api.onchange('state_id')
    def _onchange_state_id_id(self):
        if self.state_id:
            return {'domain': {'county_id': [('state_id', '=', self.state_id.id)]}}
        else:
            return {'domain': {'county_id': []}}

    def _create_partner_account(self, vals):
        for vals in vals:
            if not vals.get('country_id') and not self.country_id:
                vals['country_id'] = 8
                # raise ValidationError(
                #     _("No country defined! To create automatically the account for the customer/supplier you have to define the country!"
                #       " Go to the customer/supplier form and set the country"))
            country_id = self.env["res.country"].search([("code", "=", "AO")])
            if self.env.context.get('res_partner_search_mode') == 'customer' or vals.get('is_customer') is True:
                if vals.get('country_id') == 8:
                    seq = self.env['ir.sequence'].next_by_code(f'customer_account_{self.env.company.id}')
                else:
                    seq = self.env['ir.sequence'].next_by_code(f'customer_ext_account_{self.env.company.id}')
                code = ''

                if vals.get('type_of_account') == 'n_group':
                    if vals.get('country_id') == self.env.company.country_id.id:
                        code = self.env.company.partner_receivable_code_prefix + seq
                    else:
                        code = self.env.company.fpartner_receivable_code_prefix + seq
                elif vals.get('type_of_account') == 'group':
                    code = '31111' + seq
                account_type = self.env['account.account'].search([('account_type', '=', 'asset_receivable')])
                new_account = {
                    'name': vals['name'],
                    'code': code,
                    'account_type': account_type[0].account_type,
                    'reconcile': True,
                }
                new_account_id = self.env['account.account'].sudo().create(new_account)
                vals['property_account_receivable_id'] = new_account_id.id
                vals['sequence_code'] = seq

            if self.env.context.get('res_partner_search_mode') == 'supplier' or vals.get("is_supplier") is True:
                code = ''
                if vals.get('country_id') == 8:
                    seq = self.env['ir.sequence'].next_by_code(f'supplier_immobilized_account_{self.env.company.id}')
                else:
                    seq = self.env['ir.sequence'].next_by_code(f'supplier_ext_account_{self.env.company.id}')
                if vals.get('supplier_immobilized') is True and vals.get('type_of_immobilized') == 'corp':
                    code = '3711' + seq
                elif vals.get('supplier_immobilized') is True and vals.get('type_of_immobilized') == 'incorp':
                    code = '3712' + seq
                elif vals.get('supplier_immobilized') is True and vals.get('type_of_immobilized') == 'finan':
                    code = '3713' + seq
                elif vals.get('type_of_account') == 'n_group':
                    if vals.get('country_id') == self.env.company.country_id.id:
                        code = self.env.company.partner_payable_code_prefix + seq
                    else:
                        code = self.env.company.fpartner_payable_code_prefix + seq
                elif vals.get('type_of_account') == 'group':
                    code = '32211' + seq

                account_type = self.env['account.account'].search([('account_type', '=', 'liability_payable')])
                new_account = {
                    'name': vals['name'],
                    'code': code,
                    'account_type': account_type[0].account_type,
                    'reconcile': True,
                    # 'group_id': account_type.group_id.id
                }
                new_account_id = self.env['account.account'].sudo().create(new_account)
                vals['property_account_payable_id'] = new_account_id.id
            return vals

    @api.model_create_multi
    def create(self, vals):
        if self.env.company.country_id.code == "AO" and self.env.company.create_partner_account:
            # vals[0]["country_id"] = self.env.company.country_id.id
            vals = self._create_partner_account(vals)

        res = super(ResPartnerAng, self).create(vals)
        return res

    def write(self, vals):

        if self.env.company.country_id.code == 'AO':
            has_supplier_account = self.env.ref('l10n_ao.account_chart_321211', False)
            has_customer_account = self.env.ref('l10n_ao.account_chart_311211', False)
            for partner in self:
                if not self.env['ir.config_parameter'].sudo().get_param('dont_validate_vat'):
                    invoice_exists = self.env['account.move'].search_count(
                        [('state', 'in', ['posted', 'cancel']), ("partner_id", "=", partner.id)])
                    if invoice_exists and (vals.get('name', False) or vals.get('vat', False)):
                        if vals.get('name', False) and not partner.vat:
                            vals.pop('name')
                            raise ValidationError(_(
                                "O nome deste contacto não pode ser alterado, pois está associado a facturas já validadas pelo sistema e não possui um NIF atribuido ao mesmo\nApós atribuir o NIF "))
                        if vals.get('vat') and partner.vat not in ["9999999999", "999999999"]:
                            if partner.vat:
                                vals.pop('vat')
                                raise ValidationError(
                                    _("The NIF can´t be changed, because there are already invoices associated with it!"))
        return super(ResPartnerAng, self).write(vals)

    def get_saft_data(self):
        '''
        Returns all the fields associated to the produtions of SAFT file. Since the
        '''
        result = {
            "Customer": [],
            "Supplier": [],
        }

        for partner in self:
            if not partner.country_id:
                raise ValidationError(_("Cannot Generate SAFT data without Country. Partner %s") % partner.name)
            if not partner.city:
                raise ValidationError(_("Cannot Generate SAFT data without City. Partner %s") % partner.name)

            record = partner

            billing_address = {
                "BuildingNumber": "",
                "StreetName": record.street if record.street else "Desconhecido",
                "AddressDetail": record.contact_address[0:249],
                "City": record.city if record.city else "Desconhecido",
                "PostalCode": record.zip if record.zip else "Desconhecido",
                "Province": record.state_id.name if record.state_id else "Desconhecido",
                "Country": record.country_id.code if record.country_id else "Desconhecido"
            }

            ship_address = {
                "StreetName": record.street if record.street else "Desconhecido",
                "AddressDetail": record.contact_address[0:200],
                "City": record.city if record.city else "Desconhecido",
                "PostalCode": record.zip if record.zip else "Desconhecido",
                "Province": record.state_id.name if record.state_id else "Desconhecido",
                "Country": record.country_id.code if record.country_id else "Desconhecido"
            }

            if partner:
                result['Customer'].append({"CustomerID": partner.id if partner.id else partner.ref,
                                           "AccountID": partner.property_account_payable_id.code if partner.property_account_receivable_id.code else "Desconhecido",
                                           "CustomerTaxID": partner.vat if partner.vat else "999999999",
                                           "CompanyName": partner.name,
                                           "Contact": "",
                                           "BillingAddress": billing_address,
                                           "ShipToAddress": ship_address,
                                           "Telephone": str(partner.phone)[0:19] if partner.phone else "000000000",
                                           "Fax": "",
                                           "Email": partner.email if partner.email else "Desconhecido",
                                           "Website": partner.website if partner.website else "Desconhecido",
                                           "SelfBillingIndicator": "0"})

            if partner:
                result['Supplier'].append({"SupplierID": partner.id if partner.id else partner.ref,
                                           "AccountID": partner.property_account_payable_id.code,
                                           "SupplierTaxID": partner.vat if partner.vat else "999999999",
                                           "CompanyName": partner.name,
                                           "Contact": "",
                                           "BillingAddress": billing_address,
                                           "ShipFromAddress": ship_address,
                                           "Telephone": str(partner.phone)[0:19] if partner.phone else "000000000",
                                           "Fax": "",
                                           "Email": partner.email if partner.email else "Desconhecido",
                                           "Website": partner.website if partner.website else "Desconhecido",
                                           "SelfBillingIndicator": "0"})

        result = saft_clean_void_values("", result)

        return result

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        args = args or []

        if name:
            # Buscar pelo nome ou pelo NIF (VAT)
            partners = self.search(
                ['|', ('name', operator, name), ('vat', operator, name)] + args,
                limit=limit
            )
        else:
            partners = self.search(args, limit=limit)

        return partners.name_get()