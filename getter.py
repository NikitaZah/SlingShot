from decimal import *
from binance.client import Client
from symbol import Symbol
import pandas as pd


class Get:
    def __init__(self, client: Client):
        self.client = client

    @staticmethod
    def __candles_to_df(candles: list):
        open_time = [int(candle[0]) for candle in candles]
        close_time = [int(candle[6]) for candle in candles]
        high_price = [Decimal(candle[2]) for candle in candles]
        low_price = [Decimal(candle[3]) for candle in candles]
        open_price = [Decimal(candle[3]) for candle in candles]
        close_price = [Decimal(candle[4]) for candle in candles]
        volume = [Decimal(candle[5]) for candle in candles]
        cash_volume = [Decimal(candle[7]) for candle in candles]
        trades_number = [int(candle[8]) for candle in candles]

        data = {'open_time': open_time, 'close_time': close_time, 'high': high_price, 'low': low_price,
                'open': open_price, 'close': close_price, 'volume': volume, 'cash_volume': cash_volume,
                'trades': trades_number}
        return pd.DataFrame.from_dict(data)

    def symbols(self):
        symbols = []
        exchange_info = None
        while not exchange_info:
            try:
                exchange_info = self.client.futures_exchange_info()
            except:
                pass

        for symbol in exchange_info['symbols']:
            ticker = str(symbol['symbol'])
            if not ticker.endswith('USDT'):
                continue

            tick_size = Decimal(symbol['filters'][0]['tickSize'])
            min_qty = Decimal(symbol['filters'][1]['minQty'])
            step_size = Decimal(symbol['filters'][1]['stepSize'])

            pair = Symbol(symbol=ticker, price_step=tick_size, lot_step=step_size, min_qty=min_qty)
            symbols.append(pair)

        return symbols

    def candles(self, symbol: Symbol, interval: str, end_time=None, limit=1000, to_df=False):
        klines = []
        while limit > 1000:
            try:
                if not end_time:
                    last_klines = self.client.futures_klines(symbol=symbol.symbol, interval=interval, limit=1000)
                else:
                    last_klines = self.client.futures_klines(symbol=symbol.symbol, interval=interval, endTime=end_time,
                                                             limit=1000)

                if len(last_klines) < 1000:
                    limit = len(last_klines)
                    break

                end_time = int(last_klines[0][0]) - 1
                limit -= 1000
                last_klines.extend(klines)
                klines = last_klines.copy()
            except:
                return [] if to_df else pd.DataFrame()

        limit = max(limit, 10)
        try:
            if not end_time:
                last_klines = self.client.futures_klines(symbol=symbol, interval=interval, limit=limit)
            else:
                last_klines = self.client.futures_klines(symbol=symbol, interval=interval, endTime=end_time, limit=limit)
            last_klines.extend(klines)
            klines = last_klines.copy()
        except:
            return [] if to_df else pd.DataFrame()

        if to_df:
            return self.__candles_to_df(klines)
        return klines

    def volume(self, symbol: Symbol):
        volume = None
        while not volume:
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol.symbol)
                volume = Decimal(ticker['quoteVolume'])
            except:
                pass
        return volume

    def volatility(self, symbol: Symbol):
        volatility = None
        while not volatility:
            try:
                ticker = self.client.futures_symbol_ticker(symbol=symbol.symbol)
                volatility = Decimal(ticker['priceChangePercent'])
            except:
                pass
        return volatility


