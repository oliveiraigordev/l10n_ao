/** @odoo-module **/

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
import { useState } from "@odoo/owl";

const rpc = require("web.rpc");

function debounce(fn, delay) {
    let timer;
    return function (...args) {
        clearTimeout(timer);
        timer = setTimeout(() => fn.apply(this, args), delay);
    };
}

export class VatAutocomplete extends CharField {
    setup() {
        super.setup();
        this.state = useState({ suggestions: [] });

        // aplica debounce no input
        this.onInputHandler = debounce(this._onInputHandler.bind(this), 10);
        this.selectSuggestion = this.selectSuggestion.bind(this);
    }

    _onInputHandler(ev) {
        const value = ev.target.value;
        this.state.suggestions = [];
        this.props.record.fields.name.readonly = false;

        if (value && value.length >= 3) {
            rpc.query({
                route: "/nif/autocomplete",
                params: { term: value },
            })
                .then((result) => {
                    this.state.suggestions = result || [];
                })
                .catch((err) => {
                    console.error("Erro RPC autocomplete NIF:", err);
                });
        }
    }

    selectSuggestion(partner) {
        this.props.update(partner.vat);
        this.state.suggestions = [];

        let singular = /[a-zA-Z]/.test(partner.vat) ? 1 : 0;
        let phone = partner.phone.toString().replace('+244', '').replace(/\(/g, '').replace(/\)/g, '').replace(/ /g, '');
        if (Number.isNaN(parseInt(phone))) phone = '';

        this.props.record.update({
            name: partner.name || "",
            street: partner.address || "",
            city: partner.city || "",
            email: partner.email || "",
            phone: phone,
            mobile: phone,
            company_type: singular == 0 ? "company" : "person",
            name_readonly: true
        });
    }
}

VatAutocomplete.template = "l10n_ao_nif_search.VatAutocomplete";

registry.category("fields").add("vat_autocomplete", VatAutocomplete);