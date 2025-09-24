odoo.define('l10n_ao_report.account_report', function (require) {
'use strict';

var core = require('web.core');
var _t = core._t;
var accountReport = require('account_reports.account_report');
var unfold_first = 0;
var QWeb = core.qweb;

var l10nAoAccountReportsWidget =
accountReport.accountReportsWidget.extend({
    events: Object.assign({ }, accountReport.accountReportsWidget.prototype.events || { }, {
        'input .input_ao_filter_by_account': 'filter_by_account',
    }),
    start: async function(){
        await this._super.apply(this, arguments);
        var el_by_account = $(".input_ao_filter_by_account");

        setTimeout(function(){
            if(unfold_first == 0){
                var unfold_all = $(".js_account_report_bool_filter[data-filter='unfold_all']");
                if(unfold_all){
                    unfold_all.click();
                    unfold_first  = 1;
                }
            }
        }, 1000);
    },
    parse_report_informations: function(values) {
        this._super(...arguments);
        this.$searchview = $(QWeb.render("l10nAoAccountReports.search_bar", {report_options: this.report_options}));
        this.persist_options();
    },
    filter_by_account: function(event){
        var self = this;
        var input_data = event.target.value.trim().toLowerCase();
        this.filterOn = false;
        const reportLines = this.el.querySelectorAll('.o_account_reports_table tbody tr');
        var listOfElementsFound = [];

        if(input_data.includes(",")){
            var list_queries = input_data.split(",")
        }else{
            var list_queries = input_data.split(" ")
        }
        list_queries.forEach(query => {
            reportLines.forEach(reportLine => {
                if (reportLine.classList.length == 0) return;
                const lineNameEl = reportLine.querySelector('.account_report_line_name');
                // Only the direct text node, not text situated in other child nodes
                const displayName = lineNameEl.childNodes[0].nodeValue.trim().toLowerCase();

                const searchKey = (lineNameEl.dataset.searchKey || '').toLowerCase();
                const name = displayName.replace(searchKey, "");
                let queryFound = undefined;
                if (searchKey) {
                    queryFound = searchKey.startsWith(query.split(' ')[0]) || name.includes(query);
                } else {
                    queryFound = displayName.includes(query);
                }
                if(queryFound){
                    listOfElementsFound.push(reportLine)
                }else{
                    reportLine.classList.toggle('o_account_reports_filtered_lines', !queryFound);
                }
            });
        });
        listOfElementsFound.forEach(reportLine =>{
                if (reportLine.classList.contains('o_account_searchable_line')){
                    reportLine.classList.toggle('o_account_reports_filtered_lines', false);
                    self.filterOn = true;
                }
            });

        // Make sure all ancestors are displayed.
        const $matchingChilds = this.$('tr[data-parent-id]:not(.o_account_reports_filtered_lines):visible');
        $($matchingChilds.get().reverse()).each(function(index, el) {
            const id = $.escapeSelector(String(el.dataset.parentId));
            const $parent = self.$('.o_account_report_line[data-id="' + id + '"]');
            $parent.closest('tr').removeClass('o_account_reports_filtered_lines');
            if ($parent.hasClass('folded')) {
                $(el).addClass('o_account_reports_filtered_lines');
            }
        });
        if (this.filterOn) {
            this.$('.o_account_reports_level1.total').addClass('o_account_reports_filtered_lines');
        } else {
            this.$('.o_account_reports_level1.total').removeClass('o_account_reports_filtered_lines');
        }
        this.report_options['filter_search_bar'] = input_data;
        this.render_footnotes();


    }
});

core.action_registry.add('l10n_ao_account_report', l10nAoAccountReportsWidget);
return l10nAoAccountReportsWidget;

});
