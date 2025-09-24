from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    cash_flow_in_payment = fields.Boolean(
        "Registar Fluxo de Caixa no Pagamento",
        related="company_id.cash_flow_in_payment",
        readonly=False,
    )

    cash_flow_in_payment_register = fields.Boolean('Registar Fluxo de Caixa no Pagamento', related="company_id.cash_flow_in_payment_register",  readonly=False)
