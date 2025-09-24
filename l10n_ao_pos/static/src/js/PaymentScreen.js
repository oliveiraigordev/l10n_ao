odoo.define('l10n_ao_pos.PaymentScreen', function(require) {
    'use strict';

    const PaymentScreen = require('point_of_sale.PaymentScreen');
    const Registries = require('point_of_sale.Registries');
    const session = require('web.session');

    const L10nAoPosPaymentScreen = PaymentScreen =>
        class extends PaymentScreen {
            async _postPushOrderResolve(order, order_server_ids) {
                try {
                     if(this.env.pos.is_angola_country()) {
                      const result = await this.rpc({
                            model: 'pos.order',
                            method: 'search_read',
                            domain: [['id', 'in', order_server_ids]],
                            fields: ['pos_number','hash'],
                            context: session.user_context,
                        });
                        order.set_pos_number(result[0].pos_number || false);
                        order.set_hash(result[0].hash || false);
                        }
                        if(this.env.pos.is_angola_country()) {
                            const result = await this.rpc({
                            model: 'res.company',
                            method: 'search_read',
                            domain: [['id', '=', 1]],
                            fields: ['software_id','tax_regime_id'],
                            context: session.user_context,
                        });
                        order.set_software_id(result[0].software_id || false);
                        order.tax_regime_id(result[0].tax_regime_id.name || false);
                        }
                    }
                 finally {
                    return super._postPushOrderResolve(...arguments);
                }
            }
        };

    Registries.Component.extend(PaymentScreen, L10nAoPosPaymentScreen);

    return PaymentScreen;
});
