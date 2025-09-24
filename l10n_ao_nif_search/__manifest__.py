{
    'name': "Pesquisa NIF de Angola",
    'version': '16.0',
    'author': "Tistech Angola",
    'website': 'www.tistech.co.ao',
    'category': 'NIF/Search',
    'license': 'LGPL-3',
    'description': "Este módulo apresenta a pesquisa de NIF de Angola",
    'depends': ['base', 'account', 'l10n_ao'],
    'data': [
        'data/ir_config_parameter.xml',
        'views/res_partner_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'l10n_ao_nif_search/static/src/js/vat_autocomplete.js',
            "l10n_ao_nif_search/static/src/xml/vat_autocomplete.xml",
        ],
    },
    'installable': True,
    'auto_install': True,
}