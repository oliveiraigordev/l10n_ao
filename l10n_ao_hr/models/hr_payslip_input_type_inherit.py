from odoo import api, fields, models, tools, _
from odoo.exceptions import UserError, ValidationError


class HrPayslipInputType(models.Model):
    _inherit = 'hr.payslip.input.type'

    def write(self, values):
        if self.env.company.country_id.code == "AO":
            for record in self:
                if values.get("code"):
                    if record.code in ["HEXTRAS", "HEXTRA_50", "HEXTRA_75", "FAMI", "NAT", "FER", "HEXTRAS",
                                       "MISSING_HOUR", "FJNR", "FI", "SAL_FER", "GRATIF_FER", "ANTI", "AVPREVIOCOMP",
                                       "AVPREVIODESC"]:
                        return {}

        result = super(HrPayslipInputType, self).write(values)
        return result

    def unlink(self):
        if self.env.company.country_id.code == "AO":
            for record in self:
                # if record.code in ["HEXTRAS", "HEXTRA_50", "HEXTRA_75", "FAMI", "NAT", "FER", "HEXTRAS", "MISSING_HOUR",
                #                    "FJNR", "FI", "SAL_FER", "GRATIF_FER", "ANTI", "AVPREVIOCOMP", "AVPREVIODESC"]:
                return {}

        result = super(HrPayslipInputType, self).unlink()
        return result
