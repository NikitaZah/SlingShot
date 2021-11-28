from decimal import *
from datetime import datetime, timedelta


class TradeData:
    def __init__(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_price: Decimal, stop_loss_order,
                 stop_loss_kind: str):
        self.start_date: datetime = datetime.now()
        self.start_price = start_price
        self.original_quantity = orig_qty
        self.side = side
        self.addons = 1
        self.fixes = 0

        self.current_quantity = orig_qty
        self.current_price = start_price

        self.last_addon_time = self.start_date
        self.last_fix_time = None

        self.stop_loss_price = stop_loss_price
        self.stop_loss = stop_loss_order
        self.stop_loss_kind = stop_loss_kind

        self.stop_loss_percent = abs((self.stop_loss_price / self.start_price - 1).quantize(Decimal('0.01')))

        self.result = - self.original_quantity * self.start_price * Decimal(0.0004)     # binance fee for maker

    def addon(self, qty: Decimal, price: Decimal, price_step: Decimal):
        self.original_quantity = self.current_quantity + qty
        self.current_price = (self.current_price * self.current_quantity + price * qty) / (self.current_quantity + qty)

        if self.side == 'BUY':
            self.current_price = Decimal(self.current_price).quantize(price_step, rounding=ROUND_UP)
        else:
            self.current_price = Decimal(self.current_price).quantize(price_step, rounding=ROUND_DOWN)

        self.current_quantity = self.original_quantity
        self.last_addon_time = datetime.now()
        self.addons += 1
        self.result -= qty * price * Decimal(0.0004)

        if self.stop_loss_kind == 'STOP_MARKET':    # price where  should be moved stop loss market
            return self.current_price

    def fix(self, qty: Decimal, price: Decimal):
        self.current_quantity -= qty
        self.last_fix_time = datetime.now()
        self.fixes += 1
        self.result += (price - self.current_price) * qty if self.side == 'BUY' else -(price - self.current_price) * qty
        self.result -= qty * price * Decimal(0.0004)

        if self.stop_loss_kind == 'STOP_MARKET':    # price where should be moved stop loss market
            if self.side == 'BUY':
                if price > self.current_price * (1 + self.stop_loss_percent):
                    return self.current_price
            else:
                if price < self.current_price * (1 - self.stop_loss_percent):
                    return self.current_price


class Symbol:
    def __init__(self, symbol: str, price_step: Decimal, lot_step: Decimal, min_qty: Decimal):
        self.symbol = symbol
        self.price_step = price_step
        self.lot_step = lot_step
        self.min_qty = min_qty

        self.trend = 0
        self.day_volume = 0

        self.in_trade = False
        self.trade_data = None

    def start_trade(self, side: str, orig_qty: Decimal, start_price: Decimal, stop_loss_price: Decimal, stop_loss_order):
        self.in_trade = True
        self.trade_data = TradeData(side, orig_qty, start_price, stop_loss_price, stop_loss_order)

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

    def update(self, side: str, qty: Decimal, price: Decimal):
        if not self.in_trade:
            print(f'{self.symbol} is not in trade. Attempt to update data failed')
            return None
        if side == self.trade_data.side:
            self.trade_data.addon(qty, price, self.price_step)
        else:
            self.trade_data.fix(qty, price)
            if self.trade_data.current_quantity == 0:
                result = self.trade_data.result
                self.in_trade = False
                self.trade_data = None
                return result

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

