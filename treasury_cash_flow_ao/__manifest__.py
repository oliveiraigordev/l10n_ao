# -*- coding: utf-8 -*-
{
    'name': "Relatórios de Fluxo de Caixa e Tesouraria AO",
    'version': "16.0.1.0.0",
    'summary': "Fluxo de Caixa Direto e Relatórios de Tesouraria",
    'description': """
Este módulo contém:
- Relatório de Fluxo de Caixa Direto
- Relatório de Tesouraria (Cash Flow)
- Wizard de Tesouraria
""",
    'author': "Tis Angola",
    'license': "AGPL-3",
    'category': 'Accounting',
    'depends': [
        'account',
        'analytic',
        'report_xlsx',
    ],
    'data': [
        'security/ir.model.access.csv',
        # Views
        'views/cash_inflow_views.xml',
        # Wizard
        'wizards/treasury_cash_flow_wizard_view.xml',
        # Reports
        'report/report_layout.xml',
        'report/report_cash_direct.xml',
        'report/cash_flow_report.xml',

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}
