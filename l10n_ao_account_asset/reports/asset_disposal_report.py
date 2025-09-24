from odoo import models, api
from datetime import date
from dateutil.relativedelta import relativedelta


class AssetDisposalReport(models.AbstractModel):
    _name = 'report.l10n_ao_account_asset.asset_disposal'
    _description = 'Asset Disposal Report'

    def get_period_dates(self, period_selection):
        today = date.today()
        if period_selection == 'this_month':
            date_from = today.replace(day=1)
            date_to = (date_from + relativedelta(months=1)) - relativedelta(days=1)
        elif period_selection == 'this_quarter':
            quarter = ((today.month - 1) // 3) + 1
            date_from = date(today.year, 3 * quarter - 2, 1)
            date_to = (date_from + relativedelta(months=3)) - relativedelta(days=1)
        elif period_selection == 'this_year':
            date_from = date(today.year, 1, 1)
            date_to = date(today.year, 12, 31)
        elif period_selection == 'last_month':
            last_month = today.replace(day=1) - relativedelta(months=1)
            date_from = last_month.replace(day=1)
            date_to = (date_from + relativedelta(months=1)) - relativedelta(days=1)
        elif period_selection == 'last_quarter':
            quarter = ((today.month - 1) // 3) + 1
            if quarter == 1:
                year = today.year - 1
                quarter = 4
            else:
                year = today.year
                quarter -= 1
            date_from = date(year, 3 * quarter - 2, 1)
            date_to = (date_from + relativedelta(months=3)) - relativedelta(days=1)
        elif period_selection == 'last_year':
            year = today.year - 1
            date_from = date(year, 1, 1)
            date_to = date(year, 12, 31)
        else:
            date_from = None
            date_to = None
        return date_from, date_to

    def _get_report_values(self, docids, data=None):
        Asset = self.env['account.asset']
        company_id = self.env.company.id
        method = data.get('method')
        nature_ids = data.get('asset_nature_ids', [])
        period_selection = data.get('period_selection')
        only_posted = data.get('only_posted', True)
        unfold_all = data.get('unfold_all')
        group_by_account = data.get('group_by_account', True)

        nature_records = self.env['asset.nature'].browse(nature_ids)
        account_map = self.env['account.account'].search([
            ('id', 'in', nature_records.mapped('account_ids').ids),
            ('company_id', '=', company_id)
        ])

        if period_selection == 'custom':
            date_from = data.get('date_from')
            date_to = data.get('date_to')
        else:
            date_from, date_to = self.get_period_dates(period_selection)

        assets = Asset.search([
            ('company_id', '=', company_id),
            ('state', 'in', ['open', 'close']),
            ('active', '=', True),
            ('acquisition_date', '<=', date_to),
            '|',
            ('account_asset_id', 'in', account_map.ids),
            ('account_depreciation_id', 'in', account_map.ids),
        ])

        lines = []
        last_group = None
        
        total_acquisition_value = 0
        total_depreciation_amount = 0
        total_remaining_value = 0
        total_sale_value = 0
        total_surplus_value = 0

        for i, asset in enumerate(assets):
            acq_month = asset.acquisition_date and asset.acquisition_date.month or ''
            acq_year = asset.acquisition_date and asset.acquisition_date.year or ''
            start_month = asset.date_of_use and asset.date_of_use.month or ''
            start_year = asset.date_of_use and asset.date_of_use.year or ''
            depreciation_lines = asset.depreciation_move_ids.filtered(lambda m: m.date <= date_to and m.state == 'posted')
            depreciation_amount = depreciation_lines[-1].asset_depreciated_value
            surplus_value = asset.original_value - depreciation_amount
            remaining_value = asset.original_value - depreciation_amount - surplus_value
            account_group = self._get_parent_from_code(asset.account_asset_id.code)

            vals = {
                'account_group': account_group.code if account_group != last_group else '',
                'account_group_name': account_group.name if account_group != last_group else '',
                'no': asset.numero_patrimonio,
                'account_code': asset.account_asset_id.code,
                'name': asset.name,
                'acq_month': acq_month,
                'acq_year': acq_year,
                'start_month': start_month,
                'start_year': start_year,
                'acquisition_value': asset.original_value or '0.00',
                'depreciation_amount': depreciation_amount or '0.00',
                'remaining_value': remaining_value or '0.00',
                'sale_value': 0,
                'surplus_value': surplus_value or '0.00',
            }
            if (unfold_all and account_group == last_group) or not unfold_all:
                try:
                    lines[-1].append(vals)
                except:
                    lines.append([vals])
            else:
                lines.append([vals])
            
            last_group = account_group
        
        for group_lines in lines:
            sum_acquisition_value = sum(float(l['acquisition_value']) for l in group_lines)
            sum_depreciation_amount = sum(float(l['depreciation_amount']) for l in group_lines)
            sum_remaining_value = sum(float(l['remaining_value']) for l in group_lines)
            sum_sale_value = sum(float(l['sale_value']) for l in group_lines)
            sum_surplus_value = sum(float(l['surplus_value']) for l in group_lines)

            total_acquisition_value += sum_acquisition_value
            total_depreciation_amount += sum_depreciation_amount
            total_remaining_value += sum_remaining_value
            total_sale_value += sum_sale_value
            total_surplus_value += sum_surplus_value

            group_total = {
                'sum_acquisition_value': sum_acquisition_value,
                'sum_depreciation_amount': sum_depreciation_amount,
                'sum_remaining_value': sum_remaining_value,
                'sum_sale_value': sum_sale_value,
                'sum_surplus_value': sum_surplus_value,
            }
            group_lines.append({'is_group_total': True, 'name': last_group.name, 'totals': group_total})

        totals = {
            'total_acquisition_value': total_acquisition_value,
            'total_depreciation_amount': total_depreciation_amount,
            'total_remaining_value': total_remaining_value,
            'total_sale_value': total_sale_value,
            'total_surplus_value': total_surplus_value,
        }

        exercise_year = date_from.year if date_from.year == date_to.year else f'{date_from.year}/{date_to.year}'

        return {
            'doc_ids': docids,
            'company': self.env['res.company'].browse(company_id),
            'docs': lines,
            'totals': totals,
            'nature': [nature.code for nature in nature_records],
            'method': method,
            'exercise_year': exercise_year,
            'is_unfolded': unfold_all
        }
    
    def _get_parent_from_code(self, account_code):
        Account = self.env['account.account']
        for i in range(len(account_code) - 1, 0, -1):
            possible_parent_code = account_code[:i]
            parent = Account.search([('code', '=', possible_parent_code)], limit=1)
            if parent:
                return parent
        return False
