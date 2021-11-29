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
        self.main_trend = main_trend
        self.symbols = self.get.symbols()
        self.max_fix_times = max_fix_times

    def restore_data(self):
        pass

    def new_positions(self):
        for symbol in self.symbols:
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
                        if sl_update:
                            sl_order = self.order_controller.create_stop_loss_order(symbol,
                                                                                    price=sl_update['stop_loss'],
                                                                                    replace_old=True,
                                                                                    order_type=self.sl_type)
                            symbol.update_stop_loss(sl_order['id'], sl_order['stop_price'])

    def check_positions(self):
        for symbol in self.symbols:
            if not symbol.in_trade:
                continue

            if not symbol.trade_data.stop_loss:     # in case failed to place stop loss earlier
                sl_order = self.order_controller.create_stop_loss_order(symbol, sl_percent=self.sl_percent,
                                                                        order_type=self.sl_type)
                if sl_order:
                    symbol.update_stop_loss(sl_order['id'], sl_order['stop_price'])

            else:
                stop_loss = self.order_controller.get_order_info(symbol, symbol.trade_data.stop_loss)
                try:
                    status = stop_loss['status']
                    if status == 'FILLED':
                        qty = stop_loss['qty']
                        side = stop_loss['side']
                        price = stop_loss['price']
                        result = symbol.update(side, qty, price)['result']    # should save it into statistics
                        return result
                except KeyError:
                    pass

            signal = self.signal.slingshot_signal(symbol)
            if signal == 'FIX':
                fix = self.order_controller.fix_position(symbol, self.max_fix_times)
                try:
                    update = symbol.update(fix['side'], fix['qty'], fix['price'])
                    try:
                        result = update['result']
                    except KeyError:
                        pass
                except KeyError:
                    pass
            elif signal == 'CLOSE':
                close = self.order_controller.fix_position(symbol, self.max_fix_times)
                try:
                    result = symbol.update(close['side'], close['qty'], close['price'])['result']
                except KeyError:
                    pass






