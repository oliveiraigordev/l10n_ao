# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Angolan Localização Ponto de Venda',
    'odoo_version': '16.0',
    'version': '16.0.0.2',
    'category': 'Ponto de Venda',
    'sequence': 1,
    'summary': 'POS foi customizado para adaptar as necessidades de Angola',
    'description': "POS foi customizado para adaptar as necessidades de Angola",
    'author': 'Tis Tech Angola',
    'contributors': 'mateus.maquenguele@tistech.co.ao',
    'website': 'https://www.tistech.co.ao',
    'depends': [
        'l10n_ao',
        'point_of_sale'
    ],
    'data': [
        'views/pos_order_view.xml',
        'reports/pos_resume_session.xml',
        'reports/pos_a4_report.xml',
        'reports/report_action.xml',
    ],
    'assets': {
        'point_of_sale.assets': [
            'l10n_ao_pos/static/src/js/**/*',
            'l10n_ao_pos/static/src/xml/**/*.xml',
        ]},
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
}
