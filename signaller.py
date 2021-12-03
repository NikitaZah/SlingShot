import pandas as pd
from finta import TA
from getter import Get
from symbol import Symbol
from decimal import *


class TechAnalysis(TA):
    def slingshot(self, ohlc: pd.DataFrame, fast_length: int = 38, slow_length: int = 62):
        ema_slow = self.EMA(ohlc, slow_length, adjust=False)
        ema_fast = self.__ewm(ohlc, fast_length, adjust=False)
        trend = (ema_fast - ema_slow).dropna()
        return trend

    def stoch_rsi(self, ohlc: pd.DataFrame, length: int = 14):
        smooth_k, smooth_d = 3, 3
        rsi1 = self.RSI(ohlc, length, adjust=False)
        stoch = self.STOCH(pd.DataFrame({'close': rsi1, 'high': rsi1, 'low': rsi1}), length)
        k = self.SMA(pd.DataFrame(stoch, columns=['stoch']), smooth_k, column='stoch')
        d = self.SMA(pd.DataFrame(k, columns=['k']), smooth_d, column='k')
        return k, d


class BaseSignal:
    def __init__(self, symbol: Symbol, get: Get, trend, required_volume: Decimal, required_volatility: Decimal,
                 extra_fix_signal_percent: Decimal):
        self.get = get
        self.symbol = symbol
        self.main_trend = trend
        self.required_volume = required_volume
        self.required_volatility = required_volatility
        self.extra_fix_signal_percent = extra_fix_signal_percent
        self.TA = TechAnalysis()

    def __open_signal(self, candles: pd.DataFrame):
        return 'NEUTRAL'

    def __close_signal(self, candles: pd.DataFrame):
        return 'NEUTRAL'

    def __fix_signal(self, candles: pd.DataFrame):
        return 'NEUTRAL'


class Signal(BaseSignal):
    def __stoch_signal(self, candles: pd.DataFrame):
        k_line, d_line = self.TA.stoch_rsi(candles)

        if d_line[d_line.size - 1] > k_line[k_line.size - 1] > 80:
            return 'SELL'
        if d_line[d_line.size - 1] < k_line[k_line.size - 1] < 20:
            return 'BUY'
        if d_line[d_line.size - 1] < k_line[k_line.size - 1]:
            return 'CLOSE_BUY'
        if d_line[d_line.size - 1] > k_line[k_line.size - 1]:
            return 'CLOSE_SELL'
        else:
            return 'NEUTRAL'

    def __slingshot_signal(self, candles: pd.DataFrame):
        trend = self.TA.slingshot(candles)
        current_trend = trend.iloc[trend.size - 1]

        if current_trend * self.main_trend > 0:
            slow_ema = self.TA.EMA(candles, 62, adjust=False)
            last_slow_ema = slow_ema.iloc[slow_ema.size - 2]

            last_close = candles['close'].iloc[candles['close'].size - 2]

            if current_trend > 0:
                if last_close < last_slow_ema:
                    return 'BUY'
            if current_trend < 0:
                if last_close > last_slow_ema:
                    return 'SELL'
        return 'NEUTRAL'

    def __open_signal(self, candles: pd.DataFrame):
        signal1 = self.__stoch_signal(candles)
        signal2 = self.__slingshot_signal(candles)

        if signal1 == 'BUY' and signal2 == 'BUY':
            return 'BUY'
        elif signal1 == 'SELL' and signal2 == 'SELL':
            return 'SELL'
        else:
            return 'NEUTRAL'

    def __fix_signal(self, candles: pd.DataFrame):
        if self.symbol.trade_data.fix_allowed():
            signal = self.__stoch_signal(candles)
            if signal == 'BUY' and self.symbol.trade_data.close_side == 'BUY':
                return 'BUY'
            elif signal == 'SELL' and self.symbol.trade_data.close_side == 'SELL':
                return 'SELL'
        return 'NEUTRAL'

    def __extra_fix_signal(self, price):    # valid even if symbol.trade_data.fix_allowed() == False
        if self.symbol.trade_data.close_side == 'SELL':
            if not self.symbol.trade_data.last_fix_price:
                if price > (1 + self.extra_fix_signal_percent) * self.symbol.trade_data.current_price:
                    return 'SELL'
            else:
                if price > (1 + self.extra_fix_signal_percent) * self.symbol.trade_data.last_fix_price:
                    return 'SELL'
        if self.symbol.trade_data.close_side == 'BUY':
            if not self.symbol.trade_data.last_fix_price:
                if price < (1 - self.extra_fix_signal_percent) * self.symbol.trade_data.current_price:
                    return 'BUY'
            else:
                if price < (1 - self.extra_fix_signal_percent) * self.symbol.trade_data.last_fix_price:
                    return 'BUY'
        return 'NEUTRAL'

    def __close_signal(self, candles: pd.DataFrame):
        signal = self.__stoch_signal(candles)
        trend = self.TA.slingshot(candles)
        if self.symbol.trade_data.close_side == 'SELL' and trend.iloc[trend.size - 1] < 0 and signal == 'CLOSE_SELL':
            return 'SELL'
        elif self.symbol.trade_data.close_side == 'BUY' and trend.iloc[trend.size - 1] > 0 and signal == 'CLOSE_BUY':
            return 'BUY'
        return 'NEUTRAL'

    # def set_trend(self, symbol: Symbol):
    #     candles = self.get.candles(symbol, '4h', to_df=True)
    #     trend = self.TA.slingshot(candles)
    #     if trend.iloc[trend.size - 1] < 0:
    #         self.main_trend = -1
    #     else:
    #         self.main_trend = 1
    #     return self.main_trend
    #
    # def get_trend(self):
    #     return self.main_trend

    def slingshot_signal(self, create: bool, close: bool) -> str:
        candles = self.get.candles(self.symbol, '1h', to_df=True)
        closes = candles['close']
        price = closes.iloc[closes.size - 1]
        if create:
            if self.symbol.trade_or_addon_allowed(price):
                if self.get.volume(self.symbol) > self.required_volume and abs(self.get.volatility(self.symbol)) > self.required_volatility:
                    if self.main_trend == 1:
                        if self.__stoch_signal(candles) == 'BUY' and self.__slingshot_signal(candles) == 'BUY':
                            return 'BUY'
                    else:
                        if self.__stoch_signal(candles) == 'SELL' and self.__slingshot_signal(candles) == 'SELL':
                            return 'SELL'
        if close:
            if self.symbol.in_trade:
                close_signal = self.__close_signal(candles)
                if close_signal != 'NEUTRAL':
                    return 'CLOSE'
                fix_signal = self.__fix_signal(candles)
                if fix_signal != 'NEUTRAL':
                    return 'FIX'
                extra_fix_signal = self.__extra_fix_signal(price)
                return extra_fix_signal
        return 'NEUTRAL'
