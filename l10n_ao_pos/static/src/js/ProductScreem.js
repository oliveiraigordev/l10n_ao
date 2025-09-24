/** @odoo-module **/
/*
 * This file is used to register a inherited screen .
 */
const Registries = require('point_of_sale.Registries');
const ProductScreen = require('point_of_sale.ProductScreen');
const {
        onMounted
    } = owl;

const L10nAOProductScreen = (ProductScreen) => {
    class L10nAOProductScreen extends ProductScreen {
        async _onClickPay() {
                if(this.env.pos.get_order().orderlines.length > 0)
                    super._onClickPay();
                else
                    this.showPopup('ErrorPopup', {
                        title: "Produto",
                        body: "Deve adicionar produto ao carrinho antes de continuar com o pagamento..."
                    });
        }
    }
    return L10nAOProductScreen;
}

Registries.Component.extend(ProductScreen, L10nAOProductScreen);

return L10nAOProductScreen;