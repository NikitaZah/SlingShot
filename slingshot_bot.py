from getter import Get
from signaller import Signal
from order_controller import OrderController
from symbol import Symbol

from binance.client import Client
from decimal import *


class SlingShotBot:
    def __init__(self, client: Client, order_percent: Decimal, sl_percent: Decimal, sl_type: str,
                 main_trend: int = None, required_volume: Decimal = 80000000, required_volatility: Decimal = 0,
                 required_fix_percent: Decimal = Decimal('0.08'), max_fix_times: int = 6):
        self.get = Get(client)
        self.order_controller = OrderController(client)
        self.signal = Signal(self.get, main_trend, required_volume, required_volatility, required_fix_percent)
        self.order_percent = order_percent
        self.sl_percent = sl_percent
        self.sl_type = sl_type
        self.symbols = self.get.symbols()
        self.max_fix_times = max_fix_times

        if main_trend:
            self.main_trend = main_trend
        else:
            self.main_trend = self.set_trend()

    def restore_data(self):
        pass

    def set_trend(self):
        for symbol in self.symbols:
            if symbol.symbol == 'BTCUSDT':
                return self.signal.set_trend(symbol)

    def new_position(self, symbol: Symbol):
        signal = self.signal.slingshot_signal(symbol)
        if signal:
            order = self.order_controller.create_market_order(symbol, signal, self.order_percent)
            if order:
                if not symbol.in_trade:
                    sl_order = self.order_controller.create_stop_loss_order(symbol, sl_percent=self.sl_percent,
                                                                            order_type=self.sl_type)
                    try:
                        symbol.start_trade(signal, order['qty'], order['price'], sl_order['stopPrice'],
                                           sl_order['id'], self.sl_type)
                    except KeyError:
                        symbol.start_trade(signal, order['qty'], order['price'], None, None, self.sl_type)
                else:
                    sl_update = symbol.update(signal, order['qty'], order['price'])
                    if sl_update['stop_loss']:
                        sl_order = self.order_controller.create_stop_loss_order(symbol,
                                                                                price=sl_update['stop_loss'],
                                                                                replace_old=True,
                                                                                order_type=self.sl_type)
                        symbol.update_stop_loss(sl_order['id'], sl_order['stop_price'])

    def check_position(self, symbol: Symbol):
        result = self.check_stop_loss(symbol)
        if result:
            return result
        signal = self.signal.slingshot_signal(symbol)
        if signal == 'FIX':
            result = self.fix_position(symbol)
            if result:
                return result
        elif signal == 'CLOSE':
            result = self.close_position(symbol)
            if result:
                return result

    def check_stop_loss(self, symbol: Symbol):
        if not symbol.trade_data.stop_loss:  # in case failed to place stop loss earlier
            sl_order = self.order_controller.create_stop_loss_order(symbol, sl_percent=self.sl_percent,
                                                                    order_type=self.sl_type)
            if sl_order:
                symbol.update_stop_loss(sl_order['id'], sl_order['stop_price'])

        if symbol.trade_data.stop_loss:
            stop_loss = self.order_controller.get_order_info(symbol, symbol.trade_data.stop_loss)
            try:
                status = stop_loss['status']
                if status == 'FILLED':
                    qty = stop_loss['qty']
                    side = stop_loss['side']
                    price = stop_loss['price']
                    result = symbol.update(side, qty, price)['result']  # should save it into statistics
                    return result
            except KeyError:
                pass

    def fix_position(self, symbol: Symbol):
        fix = self.order_controller.fix_position(symbol, self.max_fix_times)
        try:
            update = symbol.update(fix['side'], fix['qty'], fix['price'])

            if update['closed']:
                result = update['result']
                self.order_controller.cancel_order(symbol, symbol.trade_data.stop_loss)
                symbol.close_position()
                return result
            elif update['stop_loss']:
                sl_order = self.order_controller.create_stop_loss_order(symbol, price=update['stop_loss'],
                                                                        replace_old=True,
                                                                        order_type=self.sl_type)
                symbol.update_stop_loss(sl_order['id'], sl_order['stopPrice'])
        except KeyError:
            pass

    def close_position(self, symbol: Symbol):
        close = self.order_controller.close_position(symbol)
        try:
            result = symbol.update(close['side'], close['qty'], close['price'])['result']
            symbol.close_position()
            return result
        except KeyError:
            pass

    def func1(self):
        for symbol in self.symbols:
            self.new_position(symbol)

    def func2(self):
        for symbol in self.symbols:
            if symbol.in_trade:
                result = self.check_position(symbol)



