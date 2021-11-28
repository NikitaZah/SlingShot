import pandas as pd
from getter import Get
from symbol import Symbol


class Signal:
    def __init__(self, get: Get, trend: int = None):
        self.get = get
        self.main_trend = trend

    @staticmethod
    def __ewm(source: pd.DataFrame, length: int) -> pd.DataFrame:
        res = source.ewm(span=length, adjust=False).mean()
        return res

    @staticmethod
    def __rma(source: pd.DataFrame, length: int) -> pd.DataFrame:
        res = source.ewm(com=length - 1, adjust=False).mean()
        return res

    @staticmethod
    def __sma(source: pd.DataFrame, length: int) -> pd.DataFrame:
        res = source.rolling(length).mean()
        return res

    @staticmethod
    def __stoch(source: pd.DataFrame, length: int):
        lowest = source['low'].rolling(window=length).min()
        highest = source['high'].rolling(window=length).max()

        res = 100 * (source['close'] - lowest) / (highest - lowest)
        return res

    def __rsi(self, source: pd.DataFrame, length: int) -> pd.DataFrame:
        delta = source.diff()
        up = delta.clip(lower=0)
        down = -1 * delta.clip(upper=0)
        rma_up = self.__rma(up, length)
        rma_down = self.__rma(down, length)
        rs = rma_up / rma_down
        return rs

    def __stoch_rsi(self, source: pd.DataFrame, length: int):
        smooth_k, smooth_d = 3, 3
        rsi1 = self.__rsi(source['close'], length)
        k = self.__sma(self.__stoch(pd.DataFrame({'close': rsi1, 'high': rsi1, 'low': rsi1}), length), smooth_k)
        d = self.__sma(k, smooth_d)
        return k, d

    def __slingshot(self, source: pd.DataFrame) -> pd.DataFrame:
        closes = source['close']
        ema_slow = self.__ewm(closes, 62)
        ema_fast = self.__ewm(closes, 38)
        trend = (ema_fast - ema_slow).dropna()
        return trend

    def __buy_signal(self, candles: pd.DataFrame):
        slow_ewm = self.__ewm(candles['close'], 62)

        if candles['close'].iloc[candles['close'].size - 2] < slow_ewm.iloc[slow_ewm.size - 2]:
            k_line, d_line = self.__stoch_rsi(candles, 14)
            if d_line[d_line.size - 1] < k_line[k_line.size - 1] < 20:
                return True
        return False

    def __sell_signal(self, candles):
        slow_ewm = self.__ewm(candles['close'], 62)

        if candles['close'].iloc[candles['close'].size - 2] > slow_ewm.iloc[slow_ewm.size - 2]:
            k_line, d_line = self.__stoch_rsi(candles, 14)
            if d_line[d_line.size-1] > k_line[k_line.size-1] > 80:
                return True
        return False

    def __fix_signal(self, candles):
        k_line, d_line = self.__stoch_rsi(candles, 14)
        if self.main_trend == 1:
            if d_line[d_line.size - 1] > k_line[k_line.size - 1] > 80:
                return True
        if self.main_trend == -1:
            if d_line[d_line.size - 1] < k_line[k_line.size - 1] < 20:
                return True
        return False

    def __close_signal(self, candles):
        k_line, d_line = self.__stoch_rsi(candles, 14)


    def set_trend(self, symbol: Symbol):
        candles = self.get.candles(symbol, '4h', to_df=True)
        trend = self.__slingshot(candles)
        if trend.iloc[trend.size - 1] < 0:
            self.main_trend = -1
        else:
            self.main_trend = 1

    def get_trend(self):
        return self.main_trend

    def slingshot_signal(self, symbol: Symbol):
        pass







