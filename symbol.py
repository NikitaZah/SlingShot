from decimal import *
from datetime import datetime, timedelta


class BaseTradeData:
    def __init__(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_order: int = None,
                 stop_loss_price: Decimal = None, stop_loss_type: str = None, take_profit_order: int = None,
                 take_profit_price: Decimal = None):
        self.start_date: datetime = datetime.now()
        self.side = side
        self.start_price = start_price
        self.original_quantity = orig_qty
        self.current_quantity = orig_qty
        self.current_price = start_price

        self.stop_loss_price = stop_loss_price
        self.stop_loss = stop_loss_order
        self.stop_loss_type = stop_loss_type
        self.rake_profit_price = take_profit_price
        self.take_profit = take_profit_order
        self.result = Decimal(0)     # redefine depending on market/limit order and current commission fee

        if self.side == 'BUY':
            self.close_side = 'SELL'
        else:
            self.close_side = 'BUY'

    def new_order(self, side: str, qty: Decimal, price: Decimal, price_step: Decimal):
        if side == self.side:
            return self.addon(qty, price, price_step)
        if side == self.close_side:
            return self.fix(qty, price)

    def fix(self, qty: Decimal, price: Decimal):
        self.current_quantity -= qty
        self.result += (price - self.current_price) * qty if self.side == 'BUY' else -(price - self.current_price) * qty
        #   add commission fee to current result

        return {'closed': self.current_quantity == Decimal(0)}

    def addon(self, qty: Decimal, price: Decimal, price_step: Decimal):
        self.current_price = (self.current_price * self.current_quantity + price * qty) / (self.current_quantity + qty)

        if self.side == 'BUY':
            self.current_price = Decimal(self.current_price).quantize(price_step, rounding=ROUND_UP)
        else:
            self.current_price = Decimal(self.current_price).quantize(price_step, rounding=ROUND_DOWN)

        self.current_quantity += qty
        # add commission fee to result

        return {'price': self.current_price, 'qty': self.current_quantity}

    def statistics(self):
        return {
            'start_date': self.start_date,
            'side': self.side,
            'max_qty': self.original_quantity,
            'current_qty': self.current_quantity,
            'result': self.result
        }


class TradeData(BaseTradeData):
    def __init__(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_price, stop_loss_order,
                 stop_loss_type: str):
        super(TradeData, self).__init__(side, orig_qty, start_price, stop_loss_price, stop_loss_order, stop_loss_type)
        self.addons = 1
        self.fixes = 0
        self.last_addon_time = self.start_date
        self.last_fix_time = None
        self.last_fix_price = None

        self.stop_loss_percent = abs((self.stop_loss_price / self.start_price - 1).quantize(Decimal('0.01')))
        self.result = - self.original_quantity * self.start_price * Decimal(0.0004)     # binance fee for maker

    def addon(self, qty: Decimal, price: Decimal, price_step: Decimal):
        self.last_addon_time = datetime.now()
        self.addons += 1
        self.result -= qty * price * Decimal(0.0004)
        self.original_quantity = self.current_quantity + qty
        return super(TradeData, self).addon(qty, price, price_step)

    def fix(self, qty: Decimal, price: Decimal):
        self.last_fix_time = datetime.now()
        self.fixes += 1
        self.last_fix_price = price
        self.result -= qty * price * Decimal(0.0004)
        return super(TradeData, self).fix(qty, price)

    def fix_allowed(self):
        return self.last_addon_time < datetime.now() - timedelta(hours=3)

    def addon_allowed(self, price: Decimal):
        if self.side == 'BUY':
            return self.current_price * Decimal('1.08') < price
        else:
            return self.current_price * Decimal('0.92') > price

    def statistics(self):
        return {
            'start_date': self.start_date,
            'close_date': self.last_fix_time,
            'side': self.side,
            'max_qty': self.original_quantity,
            'current_qty': self.current_quantity,
            'total_addons': self.addons,
            'total_fixes': self.fixes,
            'result': self.result
        }


class BaseSymbol:
    def __init__(self, symbol: str, price_step: Decimal, lot_step: Decimal, min_qty: Decimal):
        self.symbol = symbol
        self.price_step = price_step
        self.lot_step = lot_step
        self.min_qty = min_qty

        self.in_trade = False
        self.trade_data = None

    # override this method using TradeData(BaseTradeData) object
    def start_trade(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_price: Decimal = None,
                    stop_loss_order: int = None, stop_loss_type: str = None, take_profit_order: int = None,
                    take_profit_price: Decimal = None):
        self.in_trade = True
        self.trade_data = BaseTradeData(side, orig_qty, start_price, stop_loss_price, stop_loss_order, stop_loss_type,
                                        take_profit_order, take_profit_price)

    def stop_trade(self):
        result = self.trade_data.statistics()
        self.in_trade = False
        self.trade_data = None
        return result

    def update_trade_data(self, order: dict = None, new_sl: dict = None, new_tp: dict = None):
        if not self.in_trade:
            return
        if order:
            self.trade_data.new_order(order['side'], order['qty'], order['price'], self.price_step)
        if new_sl:
            self.trade_data.stop_loss = new_sl['order_id']
            self.trade_data.stop_loss_price = new_sl['price']
        if new_tp:
            self.trade_data.take_profit = new_tp['order_id']
            self.trade_data.take_profit_price = new_tp['price']


class Symbol(BaseSymbol):
    def start_trade(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_price: Decimal = None,
                    stop_loss_order: int = None, stop_loss_type: str = None, take_profit_order: int = None,
                    take_profit_price: Decimal = None):
        self.in_trade = True
        self.trade_data = TradeData(side, orig_qty, start_price, stop_loss_price, stop_loss_order, stop_loss_type)

    def fix_qty(self, parts: int):
        if not self.in_trade:
            print(f'{self.symbol} is not in trade. Attempt to get fix quantity failed')
            return None

        qty = Decimal(self.trade_data.original_quantity / parts).quantize(self.lot_step, rounding=ROUND_DOWN)

        if qty < self.min_qty:
            qty = self.min_qty

        if self.trade_data.current_quantity - qty < self.min_qty:
            qty = self.trade_data.current_quantity
        return qty

    def close_qty(self):
        if not self.in_trade:
            print(f'{self.symbol} is not in trade. Attempt to get close quantity failed')
            return None
        return self.trade_data.current_quantity

    def quantity(self, price: Decimal, quote_qty: Decimal):
        qty = (quote_qty / price).quantize(self.lot_step, rounding=ROUND_DOWN)
        if qty < self.min_qty:
            qty = self.min_qty
        return qty

    def sl_price(self, percent: Decimal):
        if self.trade_data.side == 'SELL':
            price = self.trade_data.current_price * Decimal(1 + percent)
        else:
            price = self.trade_data.current_price * Decimal(1 - percent)

        return price.quantize(self.price_step)

    def trade_or_addon_allowed(self, price: Decimal):
        if not self.in_trade:
            return True
        else:
            return self.trade_data.addon_allowed(price)
