import pandas as pd
from datetime import datetime
from pandas import DataFrame

import talib.abstract as ta

from freqtrade.strategy import (
    IStrategy,
    Trade,
    informative,
    IntParameter,
    DecimalParameter,
    stoploss_from_absolute,
)


class MomentumStrategy(IStrategy):

    INTERFACE_VERSION = 3

    # ============================================================
    # 基本设置
    # ============================================================

    timeframe = "1h"

    # Recursive analysis 已证明 200 根足够稳定
    startup_candle_count = 200

    can_short = False

    # 不设置固定止盈
    # 让真正的趋势盈利单继续运行
    minimal_roi = {}

    use_exit_signal = True
    process_only_new_candles = True

    # ------------------------------------------------------------
    # 风险管理
    #
    # -8% 只是绝对保护底线
    # 正常情况下 custom_stoploss() 会用 ATR 设置更近的止损
    # ------------------------------------------------------------

    stoploss = -0.05

    use_custom_stoploss = False

    # 不再额外使用普通 trailing stop
    # ATR custom stoploss 本身已经会动态移动
    trailing_stop = False


    # ============================================================
    # Hyperopt 参数：初始突破入场
    # ============================================================

    # 不再设置 RSI upper limit
    #
    # 原 2017-2019 Hyperopt:
    # RSI low = 60
    #
    # 搜索范围保留一定弹性
    rsi_entry_low = IntParameter(
        55,
        70,
        default=60,
        space="enter",
        optimize=True
    )

    # 成交量过滤
    volume_multiplier = DecimalParameter(
        0.70,
        1.50,
        default=0.95,
        decimals=2,
        space="enter",
        optimize=True
    )

    # 突破幅度
    #
    # 0.000 = 突破过去20h高点即可
    # 0.005 = 至少再突破0.5%
    breakout_buffer = DecimalParameter(
        0.000,
        0.010,
        default=0.000,
        decimals=3,
        space="enter",
        optimize=True
    )

    # ADX趋势强度
    adx_min = IntParameter(
        15,
        35,
        default=20,
        space="enter",
        optimize=True
    )


    # ============================================================
    # Hyperopt 参数：趋势重新入场
    # ============================================================

    # 回调后重新站上EMA20时，
    # RSI要求可以比初始突破稍低
    reentry_rsi_low = IntParameter(
        50,
        65,
        default=55,
        space="enter",
        optimize=True
    )

    # Re-entry不要求像第一次突破那样强烈放量
    reentry_volume_multiplier = DecimalParameter(
        0.50,
        1.20,
        default=0.80,
        decimals=2,
        space="enter",
        optimize=True
    )


    # ============================================================
    # ATR Risk 参数
    # ============================================================

    atr_stop_mult = DecimalParameter(
        1.5,
        4.0,
        default=2.5,
        decimals=1,
        space="risk",
        optimize=True
    )


    # ============================================================
    # 4H 大周期趋势
    #
    # Freqtrade会把这里计算出来的列自动合并到1h dataframe：
    #
    # ema50_4h
    # ema200_4h
    #
    # ============================================================

    @informative("4h")
    def populate_indicators_4h(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        dataframe["ema50"] = ta.EMA(
            dataframe,
            timeperiod=50
        )

        dataframe["ema200"] = ta.EMA(
            dataframe,
            timeperiod=200
        )

        return dataframe


    # ============================================================
    # 1H 指标
    # ============================================================

    def populate_indicators(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        # --------------------------------------------------------
        # 趋势
        # --------------------------------------------------------

        dataframe["ema20"] = ta.EMA(
            dataframe,
            timeperiod=20
        )

        dataframe["ema50"] = ta.EMA(
            dataframe,
            timeperiod=50
        )


        # --------------------------------------------------------
        # Momentum
        # --------------------------------------------------------

        dataframe["rsi"] = ta.RSI(
            dataframe,
            timeperiod=14
        )


        # --------------------------------------------------------
        # Trend strength
        # --------------------------------------------------------

        dataframe["adx"] = ta.ADX(
            dataframe,
            timeperiod=14
        )


        # --------------------------------------------------------
        # ATR volatility
        # --------------------------------------------------------

        dataframe["atr"] = ta.ATR(
            dataframe,
            timeperiod=14
        )


        # --------------------------------------------------------
        # 过去20小时最高价格
        #
        # shift(1)：
        # 当前K线不能参与自己的突破判断
        # --------------------------------------------------------

        dataframe["high_20"] = (
            dataframe["high"]
            .rolling(20)
            .max()
            .shift(1)
        )


        # --------------------------------------------------------
        # 过去20小时平均成交量
        # --------------------------------------------------------

        dataframe["volume_ma20"] = (
            dataframe["volume"]
            .rolling(20)
            .mean()
            .shift(1)
        )

        return dataframe


    # ============================================================
    # ENTRY
    # ============================================================

    def populate_entry_trend(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        # ========================================================
        # 4H Bull Regime
        #
        # 大周期 EMA50 > EMA200
        # 才允许在1h追涨
        # ========================================================

        bull_regime = (
            dataframe["ema50_4h"]
            > dataframe["ema200_4h"]
        )

        # ========================================================
        # 20H Breakout Level
        # ========================================================

        breakout_level = (
            dataframe["high_20"]
            * (1 + self.breakout_buffer.value)
        )


        # ========================================================
        # 真正的“新突破”
        #
        # 当前突破
        # 但上一根还没有突破
        # ========================================================

        fresh_breakout = (
            (
                dataframe["close"]
                > breakout_level
            )
            &
            (
                dataframe["close"].shift(1)
                <= breakout_level.shift(1)
            )
        )


        # ========================================================
        # Entry A：
        # 初始 Momentum Breakout
        # ========================================================

        breakout_entry = (

            # 大周期牛市
            bull_regime

            # 1H趋势向上
            & (
                dataframe["ema20"]
                > dataframe["ema50"]
            )

            # 真正出现20小时突破
            & fresh_breakout

            # RSI只要求强
            # 不再限制上限
            & (
                dataframe["rsi"]
                > self.rsi_entry_low.value
            )

            # ADX确认趋势强度
            & (
                dataframe["adx"]
                > self.adx_min.value
            )

            # 成交量确认
            & (
                dataframe["volume"]
                >
                dataframe["volume_ma20"]
                * self.volume_multiplier.value
            )

            & (dataframe["volume"] > 0)
        )


        dataframe.loc[
            breakout_entry,
            [
                "enter_long",
                "enter_tag"
            ]
        ] = (
            1,
            "20h_breakout"
        )


        # ========================================================
        # Entry B：
        # Trend Re-entry
        #
        # 已经处于大牛趋势，
        # 前面因为回调退出，
        # 现在重新站上EMA20。
        #
        # 目的：
        # 不要要求每次重新出现20h超级突破，
        # 避免牛市回调后长期空仓。
        # ========================================================

        cross_back_above_ema20 = (
            (
                dataframe["close"]
                > dataframe["ema20"]
            )
            &
            (
                dataframe["close"].shift(1)
                <= dataframe["ema20"].shift(1)
            )
        )


        reentry = (

            bull_regime

            & (
                dataframe["ema20"]
                > dataframe["ema50"]
            )

            # 回调后重新站上EMA20
            & cross_back_above_ema20

            # 动量恢复
            & (
                dataframe["rsi"]
                > self.reentry_rsi_low.value
            )

            # 趋势仍有一定强度
            & (
                dataframe["adx"]
                > self.adx_min.value
            )

            # Re-entry成交量要求略宽松
            & (
                dataframe["volume"]
                >
                dataframe["volume_ma20"]
                * self.reentry_volume_multiplier.value
            )

            # 如果这一根本身就是20h breakout
            # 应优先标记成 breakout，而不是 reentry
            & (~fresh_breakout)

            & (dataframe["volume"] > 0)
        )


        dataframe.loc[
            reentry,
            [
                "enter_long",
                "enter_tag"
            ]
        ] = (
            1,
            "trend_reentry"
        )

        return dataframe


    # ============================================================
    # EXIT
    #
    # 删除 RSI Exit
    #
    # 不再因为 RSI 临时下跌退出。
    #
    # 只有：
    #
    # 连续3根1h Close < EMA20
    #
    # 才认为趋势真正破坏。
    #
    # ============================================================

    def populate_exit_trend(
        self,
        dataframe: DataFrame,
        metadata: dict
    ) -> DataFrame:

        ema20_failed_3h = (

            (
                dataframe["close"]
                < dataframe["ema20"]
            )

            &

            (
                dataframe["close"].shift(1)
                < dataframe["ema20"].shift(1)
            )

            &

            (
                dataframe["close"].shift(2)
                < dataframe["ema20"].shift(2)
            )
        )


        dataframe.loc[
            (
                ema20_failed_3h
                & (dataframe["volume"] > 0)
            ),

            [
                "exit_long",
                "exit_tag"
            ]

        ] = (
            1,
            "ema20_3h_failed"
        )

        return dataframe


    # ============================================================
    # ATR CUSTOM STOPLOSS
    #
    # 与固定 -5% 不同：
    #
    # 高波动市场
    # → 止损距离更宽
    #
    # 低波动市场
    # → 止损距离更近
    #
    # ATR距离限制在：
    #
    # 2.5% ～ 7%
    #
    # stoploss = -8%
    # 只是最极端的硬保护底线。
    #
    # ============================================================

    