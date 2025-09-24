from odoo import models, fields
from odoo.exceptions import UserError


class DisposedAssetReport(models.AbstractModel):
    _name = "report.l10n_ao_account_asset.disposed_asset"
    _description = "Printing the disposed assets"

    def _get_report_values(self, docids, data):
        docs = self.env["account.asset"].browse(docids)
        if not all(item.disposal_date for item in docs):
            raise UserError("Este relatório é destinado aos Ativos já Abatidos!")

        docs_data = {
            doc.id: {
                'exercicio': doc.disposal_date.year
            } for doc in docs
        }

        return {
            "docs": docs,
            "today": fields.Date.today().strftime("%d-%m-%Y"),
            "data": docs_data
        }
