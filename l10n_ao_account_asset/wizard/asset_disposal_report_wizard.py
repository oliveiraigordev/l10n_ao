from odoo import models, fields, api
from odoo.exceptions import UserError


class AssetDisposalReportWizard(models.TransientModel):
    _name = 'asset.disposal.report.wizard'
    _description = 'Asset Disposal Report Wizard'

    period_selection = fields.Selection(
        selection=[
            ('this_month', 'Este Mês'),
            ('this_quarter', 'Este Trimestre'),
            ('this_year', 'Este Ano'),
            ('last_month', 'Último Mês'),
            ('last_quarter', 'Último Trimestre'),
            ('last_year', 'Último Ano'),
            ('custom', 'Período Personalizado')
        ],
        string='Período',
        default="this_month",
    )
    method = fields.Selection(
        selection=[
            ('linear', 'Linear'),
            ('degressive', 'Decrescente'),
            ('degressive_then_linear', 'Decrescente depois Linear')
        ],
        string='Método',
        default='linear',
    )
    date_from = fields.Date(string='Data de Início')
    date_to = fields.Date(string='Data de Fim')
    only_posted = fields.Boolean(string='Apenas Movimentos Lançados', default=True)
    unfold_all = fields.Boolean(string='Desdobrar Tudo', default=False)
    group_by_account = fields.Boolean(string='Agrupar por Conta', default=True)
    asset_nature_ids = fields.Many2many(
        comodel_name='asset.nature',
        string='Naturezas de Ativos',
        help='Selecione as naturezas de ativos para incluir no relatório.'
    )


    def _get_wizard_context(self):
        if self.period_selection == 'custom' and (not self.date_from or not self.date_to):
            raise UserError('Por favor, selecione um período personalizado válido.')

        context = {
            'period_selection': self.period_selection,
            'date_from': self.date_from,
            'date_to': self.date_to,
            'only_posted': self.only_posted,
            'unfold_all': self.unfold_all,
            'group_by_account': self.group_by_account,
            'method': self.method,
            'asset_nature_ids': self.asset_nature_ids.ids,
        }

        if context.get('asset_nature_ids'):
            records = self.env['asset.nature'].browse(context['asset_nature_ids'])
            if any(not record.account_ids for record in records):
                raise UserError('Por favor, verifique se todas as naturezas de activos selecionadas possuem contas associadas.')

        return context

    def action_generate_report(self):
        context = self._get_wizard_context()
        return self.env.ref('l10n_ao_account_asset.asset_disposal_report').report_action(self, data=context)

    def action_generate_report_pdf(self):
        context = self._get_wizard_context()
        return self.env.ref('l10n_ao_account_asset.asset_disposal_report_pdf').report_action(self, data=context)
