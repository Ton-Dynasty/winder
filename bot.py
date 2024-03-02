import asyncio
from math import exp
import os
from warnings import catch_warnings
from dotenv import load_dotenv
import logging
from typing import List, Dict, Union
from threading import Thread
from decimal import Decimal


from market_price import get_ton_usdt_price, set_ton_usdt_prices
from subscriber import subscribe
from mariadb_connector import get_alarm_from_db, get_latest_alarm_id
from ticton import TicTonAsyncClient
from strategy import ProfitableAlarm, Balance, greedy_strategy

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


async def check_balance(
    balance: Balance,
    need_base: Union[int, Decimal],
    need_quote: Union[int, Decimal],
    max_buy_num: int = 0,
):
    if balance.base_asset < need_base or balance.quote_asset < need_quote:
        logger.info("Not enough balance")
        return None
    if max_buy_num == 0:
        logger.info("Max Buy Num is 0")
        return None

    # Check if enough balance
    buy_num = 1
    for i in range(max_buy_num):
        if need_quote * (i + 1) > balance.quote_asset:
            break
        if need_base * (i + 1) > balance.base_asset:
            break
        buy_num = i + 1

    return buy_num


async def main():
    client = await TicTonAsyncClient.init(testnet=True)
    my_address = os.getenv("MY_ADDRESS", "")

    logger.info("Syncing Oracle Metadata")
    next_alarm_id, now_alarm_id = 0, 0
    while next_alarm_id != now_alarm_id + 1:
        try:
            logger.info(
                f"Syncing | Latest Alarm ID in Oracle: {next_alarm_id-1}, Now Alarm ID in Database: {now_alarm_id}"
            )
            await asyncio.sleep(10)
            await client.sync_oracle_metadata()
            next_alarm_id = client.metadata.total_alarms
            now_alarm_id = await get_latest_alarm_id()
        except Exception as e:
            logger.error(f"Error in syncing Oracle Metadata {e}")

    while True:
        try:
            logger.info("=======================")
            alarms = await get_alarm_from_db("state = 'active' AND remain_scale > 0")
            logger.info(f"Active Alarms: \n{alarms}")
            if alarms is None or len(alarms) == 0:
                logger.info("No active alarms")
                continue
            new_price = await get_ton_usdt_price()
            if new_price is None:
                continue
            new_price = round(new_price, 9)
            logger.info(f"New Price: {new_price}")

            balance_result = await client._get_user_balance(my_address)

            balance = Balance(
                base_asset=balance_result[0], quote_asset=balance_result[1]
            )
        except Exception as e:
            logger.error(f"Error in main {e}")
            continue

        profitable_alarms = []
        for alarm in alarms:
            old_price = float(alarm.price)
            price_delta = abs(new_price - old_price)
            if price_delta < float(THRESHOLD_PRICE):
                continue
            if alarm.is_mine:
                try:
                    result = await client.ring(alarm.id)
                    logger.info(f"ring result: {result}")
                    continue
                except Exception as e:
                    logger.error(f"Error in ring {e}")
                    continue
            logger.info(f"Alarm ID: {alarm.id}, Price Delta: {price_delta}")
            try:
                (
                    can_buy,
                    need_asset_tup,
                    alarm_info,
                ) = await client._estimate_wind(alarm.id, 1, new_price)

                if not can_buy:
                    logger.error("No enough balance to buy asset.")
                    continue

                if need_asset_tup is None:
                    logger.error("Need asset is None")
                    continue

                need_base_asset = need_asset_tup[0]
                need_quote_asset = need_asset_tup[1]

                if new_price > old_price:
                    max_buy_num = alarm_info.base_asset_scale
                else:
                    max_buy_num = alarm_info.quote_asset_scale
            except Exception as e:
                logger.error(f"Error in estimate wind {e}")
                continue

            buy_num = await check_balance(
                balance,
                need_base_asset,
                need_quote_asset,
                max_buy_num,
            )
            if isinstance(buy_num, int):
                profitable_alarms.append(
                    ProfitableAlarm(
                        id=alarm.id,
                        price_delta=price_delta,
                        need_base_asset=need_base_asset * buy_num,
                        need_quote_asset=need_quote_asset * buy_num,
                        buy_num=buy_num,
                    )
                )
        logger.info(f"Profitable Alarms: \n{profitable_alarms}")
        async for profitable_alarm in greedy_strategy(profitable_alarms, balance):
            try:
                result = await client.wind(
                    alarm_id=profitable_alarm.id,
                    buy_num=profitable_alarm.buy_num,
                    new_price=new_price,
                    skip_estimate=True,
                    need_base_asset=profitable_alarm.need_base_asset,
                    need_quote_asset=profitable_alarm.need_quote_asset,
                )
                logger.info(f"Wind result: {result}")
            except Exception as e:
                logger.error(f"Error in wind {e}")


if __name__ == "__main__":
    threads = [
        Thread(target=asyncio.run, args=(set_ton_usdt_prices(),), daemon=True),
        Thread(target=asyncio.run, args=(subscribe(),), daemon=True),
        Thread(target=asyncio.run, args=(main(),), daemon=True),
    ]
    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()
