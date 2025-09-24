# -*- coding: utf-8 -*-
{
    "name": "Account Asset Extension",
    "summary": """Report Asset """,
    "description": """Report Asset""",
    "author": "Tis Tech Angola",
    "website": "https://www.tistech.co.ao",
    "category": "Accounting/Accounting",
    "version": "16.0.0.3",
    "depends": ["account_asset", "hr_payroll_account", "l10n_ao_report"],
    "data": [
        "security/ir.model.access.csv",

        "data/account.asset.csv",
        "data/ir_sequence.xml",
        "data/asset_nature_data.xml",

        "reports/reinstatement_amortization_template.xml",
        "reports/disposed_asset.xml",
        "reports/assets_report.xml",
        "reports/abates_report.xml",
        "reports/reinstatement_amortization_template.xml",
        "reports/reinstatement_amortization_report.xml",
        "reports/asset_disposal_template.xml",
        "reports/asset_disposal_report.xml",

        "views/account_asset.xml",
        "views/asset_nature_view.xml",
        "views/account_asset_in_progress_view.xml",
        
        "wizard/asset_modify.xml",
        "wizard/reinstatement_amortization_report_wizard_view.xml",
        "wizard/asset_copy.xml",
        "wizard/asset_resequence_wizard_view.xml",
        "wizard/asset_disposal_report_wizard_view.xml",
        
    ],
    "assets": {
        "web.assets_backend": [
            "l10n_ao_account_asset/static/src/scss/account_asset.scss",
        ],
    },
}
