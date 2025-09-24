odoo.define('l10n_ao_pos.models', function (require) {
"use strict";
var { PosGlobalState, Order, Orderline } = require('point_of_sale.models');
const Registries = require('point_of_sale.Registries');
var rpc = require('web.rpc');  // Importa o método rpc


const L10nAOPosGlobalState = (PosGlobalState) => class L10nAOPosGlobalState extends PosGlobalState {
    is_angola_country() {
        return this.company.country.code === 'AO';
    }
    get_company_id() {
        return this.company.id;
    }
}



Registries.Model.extend(PosGlobalState,L10nAOPosGlobalState);

const L10nAOrderline = (Orderline) => class L10nAOrderline extends Orderline {
    export_for_printing() {
        // Verifica se pos_number está definido no pedido
        //if (!this.order || !this.order.pos_number) {
        //    console.warn("Ticket não será impresso, o Nº do recibo não esta definido.");
        //    return null;
        //}

        var result = super.export_for_printing(...arguments);
        result.tax_description = this.get_tax_vat();
        return result;
    }
    get_tax_vat() {
            var taxes_ids = this.get_product().taxes_id;
            var vat_tax = [];
            for (var i = 0; i < taxes_ids.length; i++) {
                var tax  = this.pos.taxes_by_id[taxes_ids[i]];
                return tax.amount;
            }
            return vat_tax;
        }
}



Registries.Model.extend(Orderline,L10nAOrderline);

const L10nAoPosOrder = (Order) => class L10nAoPosOrder extends Order {
      constructor() {
        super(...arguments);
        this.pos_number = this.pos_number || false;
        this.hash = this.hash || false;
        this.fetch_pos_number();
        this.save_to_db();
    }
     async fetch_pos_number() {
        try {
            const order_ids = await rpc.query({
                model: 'pos.order',
                method: 'search',
                args: [[['date_order', '=', this.validation_date]]],
                kwargs: { limit: 1 }
            });

            if (order_ids.length > 0) {
                const orders = await rpc.query({
                    model: 'pos.order',
                    method: 'read',
                    args: [[order_ids[0]], ['pos_number']]
                });

                if (orders.length > 0) {
                    this.pos_number = String(orders[0].pos_number);
                    this.save_to_db(); // Salva no estado do pedido
                }
            }
        } catch (error) {
            console.error("Erro ao buscar pos_number:", error);
        }
    }


    export_for_printing() {
        const result = super.export_for_printing(...arguments);
        result.pos_number = this.pos_number || 'N/A';  // Usa o número armazenado
        console.log(result.pos_number);
        result.hash = this.get_hash();
        result.software_id = this.get_software_id();
        result.tax_regime_id = this.get_regime_iva_id();
        result.company.contact_address = this.get_address();

        return result;
    }

    get_address() {
    //Prepara o endereço da empresa
        const company = this.pos.company;
        if (!company) {
            return '';
        }
        const addressParts = [];
        if (company.street) {
            addressParts.push(company.street);
        }
        if (company.street2) {
            addressParts.push(company.street2);
        }
        if (company.city) {
            addressParts.push(company.city);
        }
        if (company.state_id && company.state_id.name) {
            addressParts.push(company.state_id.name);
        }
        if (company.country_id && company.country_id.name) {
            addressParts.push(company.country_id.name);
        }
        if (company.zip) {
            addressParts.push(company.zip);
        }

        return addressParts.join(', ');
    }

    set_regime_iva_id(tax_regime_id) {
        this.tax_regime_id = tax_regime_id;
    }
    get_regime_iva_id() {
        return this.tax_regime_id;
    }
    set_software_id(software_id) {
        this.software_id = software_id;
    }
    get_software_id() {
        return this.software_id;
    }
    set_pos_number(pos_number) {
        this.pos_number = pos_number;
    }
    get_pos_number() {
        return this.pos_number;
    }
    set_hash(hash) {
        this.hash = hash;
    }
    get_hash() {
        return this.hash;
    }
     wait_for_push_order() {
      var result = super.wait_for_push_order(...arguments);
      result = Boolean(result || this.pos.is_angola_country());
      return result;
    }
}

Registries.Model.extend(Order, L10nAoPosOrder);

});

