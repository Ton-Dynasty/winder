import asyncio
import os
from dotenv import load_dotenv
import logging
from typing import List, Dict


from market_price import get_ton_usdt_price
from mariadb_connector import get_alarm_from_db, update_alarm_to_db, Alarm

from sdk import TicTonAsyncClient, FixedFloat

load_dotenv()

THRESHOLD_PRICE = os.getenv("THRESHOLD_PRICE", 0.7)

# set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

toncenter = None


async def check_balance(
    base_bal: int,
    quote_bal: int,
    need_base: int,
    need_quote: int,
    max_buy_num: int,
):
    logger.info("Check Balance")
    if base_bal < need_base:
        logger.info("Insufficient Base Asset Balance")
        return None
    if quote_bal < need_quote:
        logger.info("Insufficient Quote Asset Balance")
        return None
    if max_buy_num == 0:
        logger.info("Max Buy Num is 0")
        return None

    # Check if enough balance
    buy_num = 1
    for i in range(max_buy_num):
        if need_quote * i + 1 > quote_bal:
            break
        if need_base * i + 1 > base_bal:
            break
        buy_num = i + 1

    return buy_num


async def get_max_profit_dp(
    profitable_alarms: List[Dict], base_bal: int, quote_bal: int, fee: float = 0.55
):
    try:
        n = len(profitable_alarms)
        base_unit = 1 * 10**9
        quote_unit = 1 * 10**6
        logger.info(f"Base Bal: {base_bal}")
        logger.info(f"Quote Bal: {quote_bal}")
        logger.info(f"Fee: {fee}")
        # Initialize DP table and strategy table
        dp = [
            [
                [0 for _ in range(base_bal // base_unit + 1)]
                for _ in range(quote_bal // quote_unit + 1)
            ]
            for _ in range(n + 1)
        ]
        strategy = [
            [
                [(0, 0) for _ in range(base_bal // base_unit + 1)]
                for _ in range(quote_bal // quote_unit + 1)
            ]
            for _ in range(n + 1)
        ]

        # Fill DP table
        for i in range(1, n + 1):
            for q in range(0, quote_bal, quote_unit):
                q_idx = q // quote_unit
                for b in range(0, base_bal, base_unit):
                    b_idx = b // base_unit
                    alarm = profitable_alarms[i - 1]
                    if alarm["need_base_asset"] == 0:
                        max_buy = min(alarm["buy_num"], q // alarm["need_quote_asset"])
                    elif alarm["need_quote_asset"] == 0:
                        max_buy = min(alarm["buy_num"], b // alarm["need_base_asset"])
                    else:
                        max_buy = min(
                            alarm["buy_num"],
                            q // alarm["need_quote_asset"],
                            b // alarm["need_base_asset"],
                        )

                    for k in range(max_buy + 1):
                        cost_quote = k * alarm["need_quote_asset"]
                        cost_base = k * alarm["need_base_asset"]
                        profit = k * alarm["price_delta"] - (fee if k > 0 else 0)

                        if (
                            q >= cost_quote
                            and b >= cost_base
                            and dp[i][q_idx][b_idx]
                            < dp[i - 1][(q - cost_quote) // quote_unit][
                                (b - cost_base) // base_unit
                            ]
                            + profit
                        ):
                            dp[i][q_idx][b_idx] = (
                                dp[i - 1][(q - cost_quote) // quote_unit][
                                    (b - cost_base) // base_unit
                                ]
                                + profit
                            )
                            strategy[i][q_idx][b_idx] = (i - 1, k)

        # Retrieve the buying strategy
        final_strategy = []
        i, q, b = n, quote_bal, base_bal
        while i > 0 and (q > 0 or b > 0):
            q_idx = q // quote_unit
            b_idx = b // base_unit
            alarm_idx, quantity = strategy[i][q_idx][b_idx]
            if quantity > 0:
                alarm = profitable_alarms[alarm_idx]
                final_strategy.append(alarm)
                q -= quantity * alarm["need_quote_asset"]
                b -= quantity * alarm["need_base_asset"]
            i -= 1

        final_strategy.reverse()  # Reverse to get the order of buying

        return dp[-1][-1][-1], final_strategy
    except Exception as e:
        logger.error(f"Error while getting max profit {e}")
        return 0, []


async def main():
    global toncenter
    toncenter = await TicTonAsyncClient.init(testnet=True)
    while True:
        try:
            logger.info("=======================")
            alarms = await get_alarm_from_db("state = 'active' AND remain_scale > 0")
            logger.info(f"Active Alarms: \n{alarms}")
            if alarms is not None and len(alarms) > 0:
                new_price = await get_ton_usdt_price()
                if new_price is None:
                    return
                new_price = round(new_price, 9)
                logger.info(f"New Price: {new_price}")
                (
                    base_balance,
                    quote_balance,
                ) = await toncenter._get_user_balance()

                profitable_alarms = []
                for alarm in alarms:
                    old_price = float(alarm.price)
                    price_delta = abs(new_price - old_price)
                    if price_delta > float(THRESHOLD_PRICE):
                        if alarm.is_mine:
                            result = await toncenter.ring(alarm.id)
                            logger.info(f"Ring result: {result}")
                            continue
                        (
                            can_buy,
                            need_asset_tup,
                            alarm_info,
                        ) = await toncenter._estimate_wind(alarm.id, 1, new_price)

                        if not can_buy:
                            continue

                        need_base_asset = need_asset_tup[0]
                        need_quote_asset = need_asset_tup[1]

                        if new_price > old_price:
                            max_buy_num = alarm_info["base_asset_scale"]
                        else:
                            max_buy_num = alarm_info["quote_asset_scale"]

                        buy_num = await check_balance(
                            base_balance,
                            quote_balance,
                            need_base_asset,
                            need_quote_asset,
                            max_buy_num,
                        )
                        if isinstance(buy_num, int):
                            profitable_alarms.append(
                                {
                                    "id": alarm.id,
                                    "price_delta": price_delta,
                                    "need_base_asset": int(need_base_asset),
                                    "need_quote_asset": int(need_quote_asset),
                                    "buy_num": buy_num,
                                }
                            )

                max_profit, strategy = await get_max_profit_dp(
                    profitable_alarms, int(base_balance), int(quote_balance)
                )
                logger.info(f"Strategy: {strategy}")
                for wind_alarm in strategy:
                    result = await toncenter.wind(
                        alarm_id=wind_alarm["id"],
                        buy_num=wind_alarm["buy_num"],
                        new_price=new_price,
                        skip_estimate=True,
                        need_base_asset=wind_alarm["need_base_asset"],
                        need_quote_asset=wind_alarm["need_quote_asset"],
                    )
                    logger.info(f"Wind result: {result}")
            else:
                logger.info("No alarms found in DB")
        except Exception as e:
            logger.error(f"Error in main {e}")


if __name__ == "__main__":
    asyncio.run(main())
