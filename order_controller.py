from binance.client import Client
from binance.exceptions import BinanceAPIException
from symbol import Symbol
from decimal import *


class OrderController:
    def __init__(self, client: Client):
        self.client = client

    def __get_price(self, symbol: Symbol, trend='LONG'):
        try:
            order_book = self.client.futures_order_book(symbol=symbol.symbol, limit=5)
        except:
            return None

        if trend == 'LONG':
            price = Decimal(order_book['asks'][0][0])
        else:
            price = Decimal(order_book['bids'][0][0])
        return price

    def __define_quote_qty(self, percent: Decimal):
        try:
            account_info = self.client.futures_account_information()
        except:
            return None
        balance = Decimal(account_info['totalWalletBalance'])
        maint_margin = Decimal(account_info['totalMaintMargin'])
        total_margin = Decimal(account_info['totalMarginBalance'])

        if maint_margin/total_margin < Decimal('0.6'):
            qty = (balance * percent).quantize(Decimal('0.01'))
        elif maint_margin/total_margin < Decimal('0.7'):
            qty = (balance * percent / 2).quantize(Decimal('0.01'))
        elif maint_margin/total_margin < Decimal('0.8'):
            qty = (balance * percent / 4).quantize(Decimal('0.01'))
        else:
            qty = Decimal('0')
        return qty

    def __buy_market(self, symbol: Symbol, percent: Decimal = None, qty: Decimal = None):
        if not qty:
            price = self.__get_price(symbol, 'LONG')
            quote_qty = self.__define_quote_qty(percent=percent)
            if not price or not quote_qty:
                return None
            qty = symbol.quantity(price, quote_qty)


        try:
            order = self.client.futures_create_order(symbol=symbol.symbol, side=self.client.SIDE_BUY, quantity=qty,
                                                     type=self.client.ORDER_TYPE_MARKET)
        except:
            order = None
        return order

    def __sell_market(self, symbol: Symbol, percent: Decimal = None, qty: Decimal = None):
        if not qty:
            price = self.__get_price(symbol, 'SHORT')
            quote_qty = self.__define_quote_qty(percent=percent)
            if not price or not quote_qty:
                return None
            qty = symbol.quantity(price, quote_qty)

        try:
            order = self.client.futures_create_order(symbol=symbol.symbol, side=self.client.SIDE_SELL, quantity=qty,
                                                     type=self.client.ORDER_TYPE_MARKET)
        except:
            order = None
        return order

    def create_market_order(self, symbol: Symbol,  side: str, percent: Decimal = None, qty: Decimal = None, attempts=10):
        order = None
        if not percent and not qty:
            return None
        elif percent:
            request = {'symbol': symbol, 'percent': percent}
        else:
            request = {'symbol': symbol, 'qty': qty}

        for i in range(attempts):
            if side == 'BUY':
                order = self.__buy_market(**request)
            else:
                order = self.__sell_market(**request)
            if order:
                break
        if not order:
            return None
        else:
            order_info = self.get_order_info(symbol, order['orderId'], filling_wait=True)
            return order_info

    def create_limit_order(self, symbol: Symbol, price: Decimal, percent: Decimal, side: str, attempts=10):
        order = None
        price = price.quantize(symbol.price_step, rounding=ROUND_UP)
        quote_qty = self.__define_quote_qty(percent)
        qty = symbol.quantity(price, quote_qty)
        for i in range(attempts):
            try:
                order = self.client.futures_create_order(symbol=symbol.symbol, side=side, quantity=qty,
                                                         type=self.client.ORDER_TYPE_LIMIT,
                                                         price=price, timeInForce=self.client.TIME_IN_FORCE_GTC)
            except:
                pass
        if order:
            return self.get_order_info(symbol, order['orderId'])
        return None

    def create_stop_loss_order(self, symbol: Symbol, price: Decimal = None, sl_percent: Decimal = None, attempts=10,
                               replace_old=False, order_type: str = 'STOP_MARKET'):
        if not price:
            if not sl_percent:
                return None
            price = symbol.sl_price(sl_percent)

        if symbol.trade_data.side == self.client.SIDE_SELL:
            close_side = self.client.SIDE_BUY
        else:
            close_side = self.client.SIDE_SELL
        order = None

        # creating order request for different stop loss types: market and trailing
        request = {'symbol': symbol.symbol, 'side': close_side, 'type': order_type, 'closePosition': True}
        if order_type == 'STOP_MARKET':
            request['stopPrice'] = price
        if order_type == 'TRAILING_STOP_MARKET':
            request['callbackRate'] = sl_percent

        for i in range(attempts):
            try:
                order = self.client.futures_create_order(**request)
                break
            except:
                pass
        if not order:
            return None
        if replace_old:
            canceled = self.cancel_order(symbol, symbol.trade_data.stop_loss, attempts)
            if not canceled:
                pass
        return self.get_order_info(symbol, order['orderId'])

    def fix_position(self, symbol: Symbol, parts: int):
        qty = symbol.fix_qty(parts)
        if symbol.trade_data.side == 'BUY':
            return self.create_market_order(symbol, 'SELL', qty=qty)
        else:
            return self.create_market_order(symbol, 'BUY', qty=qty)

    def close_position(self, symbol: Symbol):
        qty = symbol.close_qty()
        if symbol.trade_data.side == 'BUY':
            return self.create_market_order(symbol, 'SELL', qty=qty)
        else:
            return self.create_market_order(symbol, 'BUY', qty=qty)

    def cancel_order(self, symbol: Symbol, order_id: int, attempts=10):
        canceled = None
        for i in range(attempts):
            try:
                canceled = self.client.futures_cancel_order(symbol=symbol.symbol, orderId=order_id)
                break
            except:
                pass
        return canceled

    def get_order_info(self, symbol: Symbol, order_id: int, filling_wait=False):
        order = None
        if filling_wait:
            waited = False
            while not waited:
                try:
                    order = self.client.futures_get_order(symbol=symbol.symbol, orderId=order_id)
                    if order["status"] == 'FILLED':
                        waited = True
                except BinanceAPIException as error:
                    if int(error.code) == -2013:    # Order does not exist
                        break
                except:
                    pass
        else:
            try:
                order = self.client.futures_get_order(symbol=symbol.symbol, orderId=order_id)
            except:
                order = None

        if order:
            order_info = {
                'status': order['status'],
                'qty': Decimal(order['executedQty']),
                'price': Decimal(order['avgPrice']),
                'id': int(order['orderId']),
                'stop_price': Decimal(order['stopPrice']),
                'side': order['side']
            }
            return order_info
        else:
            return {}
