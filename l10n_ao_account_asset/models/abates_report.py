from datetime import datetime
from collections import defaultdict

from odoo import models, fields
from odoo.tools import format_date


class AbatesReportCustomHandler(models.AbstractModel):
    _name = "abates.report.handler"
    _inherit = "account.asset.report.handler"
    _description = "Handler Mapa de Abates"

    def _query_values(self, options, prefix_to_match=None, forced_account_id=None):
        "Get the data from the database"

        self.env["account.move.line"].check_access_rights("read")
        self.env["account.asset"].check_access_rights("read")

        move_filter = f"""move.state {"!= 'cancel'" if options.get('all_entries') else "= 'posted'"}"""

        if options.get("multi_company", False):
            company_ids = tuple(self.env.companies.ids)
        else:
            company_ids = tuple(self.env.company.ids)

        query_params = {
            "date_to": options["date"]["date_to"],
            "date_from": options["date"]["date_from"],
            "company_ids": company_ids,
        }

        prefix_query = ""
        if prefix_to_match:
            prefix_query = "AND asset.name ILIKE %(prefix_to_match)s"
            query_params["prefix_to_match"] = f"{prefix_to_match}%"

        account_query = ""
        if forced_account_id:
            account_query = "AND account.id = %(forced_account_id)s"
            query_params["forced_account_id"] = forced_account_id

        analytical_query = ""
        if options.get("analytic_accounts") and not any(
            x in options.get("analytic_accounts_list", [])
            for x in options["analytic_accounts"]
        ):
            analytic_account_ids = [
                [str(account_id) for account_id in options["analytic_accounts"]]
            ]
            analytical_query = (
                "AND asset.analytic_distribution ?| array[%(analytic_account_ids)s]"
            )
            query_params["analytic_account_ids"] = analytic_account_ids

        sql = f"""
            SELECT asset.id AS asset_id,
                   asset.parent_id AS parent_id,
                   asset.name AS asset_name,
                   asset.original_value AS asset_original_value,
                   asset.currency_id AS asset_currency_id,
                   MIN(move.date) AS asset_date,
                   asset.disposal_date AS asset_disposal_date,
                   asset.acquisition_date AS asset_acquisition_date,
                   asset.method AS asset_method,
                   asset.method_number AS asset_method_number,
                   asset.method_period AS asset_method_period,
                   asset.method_progress_factor AS asset_method_progress_factor,
                   asset.state AS asset_state,
                   asset.num_ficha AS num_ficha,
                   account.code AS account_code,
                   account.name AS account_name,
                   account.id AS account_id,
                   account.company_id AS company_id,
                   COALESCE(SUM(move.depreciation_value) FILTER (WHERE move.date < %(date_from)s AND {move_filter}), 0) + COALESCE(asset.already_depreciated_amount_import, 0) AS depreciated_before,
                   COALESCE(SUM(move.depreciation_value) FILTER (WHERE move.date BETWEEN %(date_from)s AND %(date_to)s AND {move_filter}), 0) AS depreciated_during
              FROM account_asset AS asset
         LEFT JOIN account_account AS account ON asset.account_asset_id = account.id
         LEFT JOIN account_move move ON move.asset_id = asset.id
         LEFT JOIN account_move reversal ON reversal.reversed_entry_id = move.id
             WHERE asset.company_id in %(company_ids)s
               AND (asset.acquisition_date <= %(date_to)s OR move.date <= %(date_to)s)
               AND (asset.disposal_date IS NOT NULL)
               AND asset.state not in ('model', 'draft', 'cancelled')
               AND asset.asset_type = 'purchase'
               AND asset.active = 't'
               AND reversal.id IS NULL
               {prefix_query}
               {account_query}
               {analytical_query}
          GROUP BY asset.id, account.id
          ORDER BY account.code, asset.acquisition_date;
        """

        self._cr.execute(sql, query_params)
        results = self._cr.dictfetchall()
        return results

    def _query_lines(self, options, prefix_to_match=None, forced_account_id=None):
        """
        Returns a list of tuples: [(asset_id, account_id, [{expression_label: value}])]
        """
        lines = []
        asset_lines = self._query_values(
            options,
            prefix_to_match=prefix_to_match,
            forced_account_id=forced_account_id,
        )

        # Assign the gross increases sub assets to their main asset (parent)
        parent_lines = []
        children_lines = defaultdict(list)
        for al in asset_lines:
            if al["parent_id"]:
                children_lines[al["parent_id"]] += [al]
            else:
                parent_lines += [al]

        for al in parent_lines:
            # Manage the opening of the asset
            opening = (
                al["asset_acquisition_date"] or al["asset_date"]
            ) < fields.Date.to_date(options["date"]["date_from"])

            # Get the main values of the board for the asset
            depreciation_opening = al["depreciated_before"]
            depreciation_add = al["depreciated_during"]
            depreciation_minus = 0.0

            asset_opening = al["asset_original_value"] if opening else 0.0
            asset_add = 0.0 if opening else al["asset_original_value"]
            asset_minus = 0.0

            # Add the main values of the board for all the sub assets (gross increases)
            for child in children_lines[al["asset_id"]]:
                depreciation_opening += child["depreciated_before"]
                depreciation_add += child["depreciated_during"]

                opening = (
                    child["asset_acquisition_date"] or child["asset_date"]
                ) < fields.Date.to_date(options["date"]["date_from"])
                asset_opening += child["asset_original_value"] if opening else 0.0
                asset_add += 0.0 if opening else child["asset_original_value"]

            # Compute the closing values
            asset_closing = asset_opening + asset_add - asset_minus
            depreciation_closing = (
                depreciation_opening + depreciation_add - depreciation_minus
            )

            # Manage the closing of the asset
            if (
                al["asset_state"] == "close"
                and al["asset_disposal_date"]
                and al["asset_disposal_date"]
                <= fields.Date.to_date(options["date"]["date_to"])
            ):
                depreciation_minus += depreciation_closing
                depreciation_closing = 0.0
                asset_minus += asset_closing
                asset_closing = 0.0

            # Manage negative assets (credit notes)
            if al["asset_original_value"] < 0:
                asset_add, asset_minus = -asset_minus, -asset_add
                depreciation_add, depreciation_minus = (
                    -depreciation_minus,
                    -depreciation_add,
                )

            # Format the data
            # TODO This should be done in the SQL Query
            asset_id = self.env["account.asset"].search([("id", "=", al["asset_id"])])
            date_from = options["date"]["date_from"]
            date_to = options["date"]["date_to"]

            try:
                date_to = datetime.strptime(str(date_to), "%Y-%m-%d").date()
                date_from = datetime.strptime(str(date_from), "%Y-%m-%d").date()
            except ValueError:
                date_to = None
                date_from = None

            move_ids = self.env["account.move"].search(
                [
                    ("asset_id", "=", asset_id.id),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                ],
                order="date asc, id asc",
            )
            if asset_id.disposal_date and asset_id.disposal_date <= date_to:
                move_ids = move_ids[:-1]

            if move_ids:
                valor_amortizacao_acululada = move_ids[-1].asset_depreciated_value
                valor_valia = asset_id.original_value - asset_id.valor_amortizacao_acululada
                valor_contabilistico_residual = abs(asset_id.original_value - valor_amortizacao_acululada - valor_valia)
                
      
        
                columns_by_expr_label = {
                    "num_ficha": asset_id.num_ficha,
                    "conta_plano_geral": asset_id.account_depreciation_id.display_name
                    or "",
                    "descricao_ativo": al["asset_name"],
                    "acquisition_date": al["asset_acquisition_date"]
                    and format_date(self.env, al["asset_acquisition_date"])
                    or "",  # Characteristics
                    "prorata_date": format_date(self.env, asset_id.prorata_date),
                    "valores_de_aquisicao": format(asset_id.original_value, ".2f"),
                    "valor_amortizacoes_acumuladas": format(
                        valor_amortizacao_acululada, ".2f"
                    ),
                    "valor_contabilistico_residual": format(
                        valor_contabilistico_residual, ".2f"
                    ),
                    "valor_venda": format(0, ".2f"),
                    "valor_valia": format(valor_valia, ".2f"),
                }

                lines.append((al["account_id"], al["asset_id"], columns_by_expr_label))
        return lines

    def _custom_line_postprocessor(self, report, options, lines):
        for line in lines:
            for column in line["columns"]:
                if "no_format" in column and column["no_format"] == 0:
                    column_class = column.get("class") or ""
                    column["class"] = column_class + " o_asset_blank_if_zero_value"
        linhas_out = []
        for line in lines:
            if line["level"] == 5:
                line["name"] = ""
                line["columns"][2]["caret_options"] = "account_asset_line"
                linhas_out.append(line)
        return linhas_out
