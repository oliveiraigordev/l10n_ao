from odoo import models, fields, api, _


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    currency_name = fields.Char(related="currency_id.name", store=True)

    @api.constrains('product_id', 'account_id')
    def check_aml_journal_type(self):
        for aml in self:
            account_origin = aml.move_id.iva_origin_account if aml.move_id.iva_origin_account else ""
            if aml.journal_id.type in ("sale", "purchase"):
                for tax in aml.tax_ids:
                    if tax.tax_type == "IVA" and tax.amount > 0:
                        if aml.account_id.code not in account_origin:
                            account_origin = account_origin+", "+aml.account_id.code if account_origin else aml.account_id.code
                        break

                if len(account_origin) > 0:
                    aml.move_id.write({"iva_origin_account": account_origin})

    def unlink(self):
        for aml in self:
            account_origin = aml.move_id.iva_origin_account
            if account_origin and aml.journal_id.type in ("sale", "purchase"):
                if aml.account_id and aml.account_id.code in account_origin:
                    if aml.account_id.code+", " in account_origin:
                        account_origin = account_origin.replace(aml.account_id.code+", ", "")
                    else:
                        account_origin = account_origin.replace(aml.account_id.code, "")

                    aml.move_id.write({"iva_origin_account": account_origin})

        return super(AccountMoveLine, self).unlink()

