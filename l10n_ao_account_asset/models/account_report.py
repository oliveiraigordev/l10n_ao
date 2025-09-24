import markupsafe
from datetime import datetime
from collections import defaultdict

from odoo import models, fields, _
from odoo.tools import format_date, config

MAX_NAME_LENGTH = 50


class AssetsReport(models.Model):
    _inherit = "account.report"

    def _get_caret_option_view_map(self):
        view_map = super()._get_caret_option_view_map()
        view_map["account.asset.line"] = "account_asset.view_account_asset_expense_form"
        return view_map


class AccountReportColumn(models.Model):
    _inherit = "account.report"

    def export_to_pdf(self, options):
        self.ensure_one()
        # As the assets are generated during the same transaction as the rendering of the
        # templates calling them, there is a scenario where the assets are unreachable: when
        # you make a request to read the assets while the transaction creating them is not done.
        # Indeed, when you make an asset request, the controllers has to read the `ir.attachment`
        # table.
        # This scenario happens when you want to print a PDF report for the first time, as the
        # assets are not in cache and must be generated. To workaround this issue, we manually
        # commit the writes in the `ir.attachment` table. It is done thanks to a key in the context.
        if not config["test_enable"]:
            self = self.with_context(commit_assetsbundle=True)

        base_url = self.env["ir.config_parameter"].sudo().get_param(
            "report.url"
        ) or self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        rcontext = {
            "mode": "print",
            "base_url": base_url,
            "company": self.env.company,
        }

        print_mode_self = self.with_context(print_mode=True)
        print_options = print_mode_self._get_options(previous_options=options)
        body_html = print_mode_self.get_html(
            print_options,
            self._filter_out_folded_children(print_mode_self._get_lines(print_options)),
        )
        body = self.env["ir.ui.view"]._render_template(
            "account_reports.print_template",
            values=dict(rcontext, body_html=body_html),
        )
        footer = self.env["ir.actions.report"]._render_template(
            "web.internal_layout", values=rcontext
        )
        footer = self.env["ir.actions.report"]._render_template(
            "web.minimal_layout",
            values=dict(rcontext, subst=True, body=markupsafe.Markup(footer.decode())),
        )

        landscape = False
        if len(print_options["columns"]) * len(print_options["column_groups"]) > 5:
            landscape = True
        report_ids = self.env.ref(
            "l10n_ao_account_asset.abates_report_ao"
        ) | self.env.ref("l10n_ao_account_asset.assets_report_ao")
        if self.id in report_ids.ids:
            file_content = self.env["ir.actions.report"]._run_wkhtmltopdf(
                [body],
                report_ref="l10n_ao_account_asset.action_report_asset_pdf",
                footer=footer.decode(),
                landscape=landscape,
                specific_paperformat_args={
                    "data-report-margin-top": 10,
                    "data-report-header-spacing": 10,
                },
            )
        else:
            file_content = self.env["ir.actions.report"]._run_wkhtmltopdf(
                [body],
                footer=footer.decode(),
                landscape=landscape,
                specific_paperformat_args={
                    "data-report-margin-top": 10,
                    "data-report-header-spacing": 10,
                },
            )
        return {
            "file_name": self.get_default_report_filename("pdf"),
            "file_content": file_content,
            "file_type": "pdf",
        }


class AssetReportCustomHandler(models.AbstractModel):
    _inherit = "account.asset.report.handler"

    def _group_by_account(self, report, lines, options):
        """
        This function adds the grouping lines on top of each group of account.asset
        It iterates over the lines, change the line_id of each line to include the account.account.id and the
        account.asset.id.
        """
        if not lines:
            return lines
        line_vals_per_account_id = {}
        for line in lines:
            parent_account_id = line.get("assets_account_id")

            model, res_id = report._get_model_info_from_id(line["id"])
            assert model == "account.asset"

            # replace the line['id'] to add the account.account.id
            line["id"] = report._build_line_id(
                [
                    (None, "account.account", parent_account_id),
                    (None, "account.asset", res_id),
                ]
            )

            line_vals_per_account_id.setdefault(
                parent_account_id,
                {
                    # We don't assign a name to the line yet, so that we can batch the browsing of account.account objects
                    "id": report._build_line_id(
                        [(None, "account.account", parent_account_id)]
                    ),
                    "columns": [],  # Filled later
                    "unfoldable": True,
                    "unfolded": options.get("unfold_all", False),
                    "level": 1,
                    "class": "o_account_asset_contrast",
                    # This value is stored here for convenience; it will be removed from the result
                    "group_lines": [],
                },
            )["group_lines"].append(line)

        # Generate the result
        idx_monetary_columns = [
            idx_col
            for idx_col, col in enumerate(options["columns"])
            if col["figure_type"] == "monetary"
        ]
        accounts = self.env["account.account"].browse(line_vals_per_account_id.keys())
        rslt_lines = []
        for account in accounts:
            account_line_vals = line_vals_per_account_id[account.id]
            account_line_vals["name"] = f"{account.code} {account.name}"

            rslt_lines.append(account_line_vals)

            group_totals = {column_index: 0 for column_index in idx_monetary_columns}
            group_lines = report._regroup_lines_by_name_prefix(
                options,
                account_line_vals.pop("group_lines"),
                "_report_expand_unfoldable_line_assets_report_prefix_group",
                account_line_vals["level"],
                parent_line_dict_id=account_line_vals["id"],
            )

            for account_subline in group_lines:
                # Add this line to the group totals
                for column_index in idx_monetary_columns:
                    group_totals[column_index] += account_subline["columns"][
                        column_index
                    ].get("no_format", 0)

                # Setup the parent and add the line to the result
                account_subline["parent_id"] = account_line_vals["id"]
                rslt_lines.append(account_subline)

            # Add totals (columns) to the account line
            for column_index in range(len(options["columns"])):
                tot_val = group_totals.get(column_index)
                if tot_val is None:
                    account_line_vals["columns"].append({})
                else:
                    account_line_vals["columns"].append(
                        {
                            "name": report.format_value(
                                tot_val,
                                self.env.company.currency_id,
                                figure_type="monetary",
                                blank_if_zero=options["columns"][column_index][
                                    "blank_if_zero"
                                ],
                            ),
                            "no_format": tot_val,
                        }
                    )
        return rslt_lines

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
               AND (asset.disposal_date >= %(date_from)s OR asset.disposal_date IS NULL)
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

    def _generate_report_lines_without_grouping(
        self,
        report,
        options,
        prefix_to_match=None,
        parent_id=None,
        forced_account_id=None,
    ):
        all_asset_ids = set()
        all_lines_data = {}

        for (
            column_group_key,
            column_group_options,
        ) in report._split_options_per_column_group(options).items():
            # the lines returned are already sorted by account_id !
            lines_query_results = self._query_lines(
                column_group_options,
                prefix_to_match=prefix_to_match,
                forced_account_id=forced_account_id,
            )
            for account_id, asset_id, cols_by_expr_label in lines_query_results:
                line_id = (account_id, asset_id)
                all_asset_ids.add(asset_id)
                if line_id not in all_lines_data:
                    all_lines_data[line_id] = {column_group_key: []}
                all_lines_data[line_id][column_group_key] = cols_by_expr_label

        column_names = [
            "assets_date_from",
            "assets_plus",
            "assets_minus",
            "assets_date_to",
            "depre_date_from",
            "depre_plus",
            "depre_minus",
            "depre_date_to",
            "balance",
        ]
        totals_by_column_group = defaultdict(lambda: dict.fromkeys(column_names, 0.0))

        # Browse all the necessary assets in one go, to minimize the number of queries
        assets_cache = {
            asset.id: asset for asset in self.env["account.asset"].browse(all_asset_ids)
        }

        # construct the lines, 1 at a time
        lines = []
        company_currency = self.env.company.currency_id

        for (account_id, asset_id), col_group_totals in all_lines_data.items():
            all_columns = []
            for column_data in options["columns"]:
                col_group_key = column_data["column_group_key"]
                expr_label = column_data["expression_label"]
                if (
                    col_group_key not in col_group_totals
                    or expr_label not in col_group_totals[col_group_key]
                ):
                    all_columns.append({})
                    continue

                col_value = col_group_totals[col_group_key][expr_label]
                if col_value is None:
                    all_columns.append({})
                elif column_data["figure_type"] == "monetary":
                    col_value = float(col_value)
                    all_columns.append(
                        {
                            "name": report.format_value(
                                col_value,
                                company_currency,
                                figure_type="monetary",
                                blank_if_zero=column_data["blank_if_zero"],
                            ),
                            "no_format": col_value,
                        }
                    )
                else:
                    all_columns.append({"name": col_value, "no_format": col_value})

                # add to the total line
                if column_data["figure_type"] == "monetary":
                    totals_by_column_group[column_data["column_group_key"]][
                        column_data["expression_label"]
                    ] += col_value

            name = assets_cache[asset_id].name
            line = {
                "id": report._get_generic_line_id(
                    "account.asset", asset_id, parent_line_id=parent_id
                ),
                "level": 2,
                "name": name,
                "columns": all_columns,
                "unfoldable": False,
                "unfolded": False,
                "caret_options": "account_asset_line",
                "assets_account_id": account_id,
                "class": "o_account_asset_contrast_inner",
            }
            if parent_id:
                line["parent_id"] = parent_id
            if len(name) >= MAX_NAME_LENGTH:
                line["title_hover"] = name
            lines.append(line)

        return lines, totals_by_column_group

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
            info_dados = self.env["account.asset"].search([("id", "=", al["asset_id"])])
            date_from = options["date"]["date_from"]
            date_to = options["date"]["date_to"]
            lista_soma_asset_depreciated_value = []
            lista_soma_depreciation_value = []
            lista_soma_depreciation_total = []
            lista_soma_asset_remaining_value = []
            lista_soma_valores_exercicio = []
            try:
                date_to = datetime.strptime(str(date_to), "%Y-%m-%d")
                date_from = datetime.strptime(str(date_from), "%Y-%m-%d")
            except ValueError:
                date_to = None
                date_from = None

            move_ids = self.env["account.move"].search(
                [
                    ("asset_id", "=", info_dados.id),
                    ("date", ">=", date_from),
                    ("date", "<=", date_to),
                ],
                order="date asc, id asc",
            )
            if info_dados.disposal_date and info_dados.disposal_date <= date_to.date():
                move_ids = move_ids[:-1]

            for depreciation in move_ids:
                exercicio_anterior = date_from.date().year - 1
                if depreciation.date.year == exercicio_anterior:
                    lista_soma_valores_exercicio.append(depreciation.depreciation_value)
                if (
                    depreciation.date >= date_from.date()
                    and depreciation.date <= date_to.date()
                ):
                    lista_soma_asset_depreciated_value.append(
                        depreciation.asset_depreciated_value
                    )
                    lista_soma_depreciation_value.append(
                        depreciation.depreciation_value
                    )
                    lista_soma_asset_remaining_value.append(
                        depreciation.asset_remaining_value
                    )
                if depreciation.date <= date_to.date():
                    lista_soma_depreciation_total.append(
                        depreciation.depreciation_value
                    )
            soma = sum([numero for numero in lista_soma_depreciation_value])
            soma_valores_exercicio = sum(
                [numero for numero in lista_soma_valores_exercicio]
            )
            if len(lista_soma_asset_remaining_value) == 0:
                valor_contabilistico_residual = 0.00
            else:
                valor_contabilistico_residual = format(
                    lista_soma_asset_remaining_value[0], ".2f"
                )
            if float(valor_contabilistico_residual) > 0:
                valor_amortizacao_acululada = float(info_dados.original_value) - float(
                    valor_contabilistico_residual
                )
            else:
                valor_amortizacao_acululada = 0
            texto = f"{info_dados.account_depreciation_id.display_name}"

        
            if info_dados.depreciation_move_ids :
                depreciation_ids = info_dados.depreciation_move_ids[0].date
            else:
                depreciation_ids = ''

            columns_by_expr_label = {
                "num_ficha": info_dados.num_ficha,
                "conta_plano_geral": texto,
                "atividade_economica_related": info_dados.name,
                "acquisition_date": al["asset_acquisition_date"]
                and format_date(self.env, al["asset_acquisition_date"])
                or "",  # Characteristics
                "prorata_date": info_dados.prorata_date,
                "activo_importado": "",
                "vida_util_related": info_dados.vida_util_related,
                "depreciation_move_ids":  depreciation_ids,
                "valor_do_acrescimo_reavaliacao": "",
                "valor_total_reavaliado": "",
                "exercicios_anteriores": format(soma_valores_exercicio, ".2f"),
                "taxa": info_dados.taxa_anual_related,
                "taxa_corrigida": "%",
                "valores": format(soma, ".2f"),
                "valores_de_aquisicao": format(info_dados.original_value, ".2f"),
                "valor_contabilistico_residual": valor_contabilistico_residual,
                "valor_amortizacoes_acumuladas": format(
                    valor_amortizacao_acululada, ".2f"
                ),
            }

            lines.append((al["account_id"], al["asset_id"], columns_by_expr_label))
        return lines

    def _custom_options_initializer(self, report, options, previous_options=None):
        super()._custom_options_initializer(
            report, options, previous_options=previous_options
        )
        column_group_options_map = report._split_options_per_column_group(options)
        for col in options["columns"]:
            col['template'] = 'l10n_ao_account_asset.cell_template'
            col['style'] += 'white-space: normal'
            column_group_options = column_group_options_map[col["column_group_key"]]
            # Dynamic naming of columns containing dates
            if col["expression_label"] == "balance":
                col["name"] = ""  # The column label will be displayed in the subheader
            if col["expression_label"] in ["assets_date_from", "depre_date_from"]:
                col["name"] = format_date(
                    self.env, column_group_options["date"]["date_from"]
                )
            elif col["expression_label"] in ["assets_date_to", "depre_date_to"]:
                col["name"] = format_date(
                    self.env, column_group_options["date"]["date_to"]
                )
        options["custom_columns_subheaders"] = []
        options["column_headers"] = []

        options["company_vat"] = report.write_uid.company_id.vat or ""

        # Group by account by default
        groupby_activated = (previous_options or {}).get("assets_groupby_account", True)
        options["assets_groupby_account"] = groupby_activated
        # If group by account is activated, activate the hierarchy (which will group by account group as well) if
        # the company has at least one account group, otherwise only group by account
        has_account_group = self.env["account.group"].search_count(
            [("company_id", "=", self.env.company.id)], limit=1
        )
        hierarchy_activated = (previous_options or {}).get("hierarchy", True)
        options["hierarchy"] = has_account_group and hierarchy_activated or False

        prefix_group_parameter_name = (
            "account_reports.assets_report.groupby_prefix_groups_threshold"
        )
        prefix_groups_threshold = int(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param(prefix_group_parameter_name, 0)
        )
        if prefix_groups_threshold:
            options["groupby_prefix_groups_threshold"] = prefix_groups_threshold

        # Automatically unfold the report when printing it or not using prefix groups, unless some specific lines have been unfolded
        options["unfold_all"] = (
            self._context.get("print_mode") and not options.get("unfolded_lines")
        ) or (
            report.filter_unfold_all
            and (previous_options or {}).get("unfold_all", not prefix_groups_threshold)
        )
