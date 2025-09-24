from odoo import fields, models, api, _
from odoo.exceptions import Warning, UserError, ValidationError


class SalaryCategory(models.Model):
    _inherit = 'hr.salary.rule.category'

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            for record in self:
                if values.get("code"):
                    if record.code in ["BAS", "ABO", "HEXTRA", "DED", "FALTA", "COMP", "ABOINSS", "ABOIRT",
                                       "ABOINSSIRT",
                                       "DEDINSSIRT", "INSS", "IRT","INSS8"]:
                        return {}
                        # raise UserError(
                        #     _('This category rule as Protected dont is Possible to update code.\n Contact System Administrator.'))

        result = super(SalaryCategory, self).write(values)
        return result

    def unlink(self):
        if self.env.company.country_id.code == "AO":
            for record in self:
                if record.code in ["BAS", "ABO", "HEXTRA", "DED", "FALTA", "COMP", "ABOINSS", "ABOIRT", "ABOINSSIRT",
                                   "DEDINSSIRT", "INSS", "IRT","INSS8"]:
                    return {}
                    # raise UserError(_(
                    #     "The category %s was not deleted, as it has an associated Salary Rules. Contact the administrator") % record.name)
                super(SalaryCategory, record).unlink()
        else:
            super(SalaryCategory, self).unlink()
        return {}
