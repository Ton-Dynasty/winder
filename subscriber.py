from sdk import TicTonAsyncClient, FixedFloat
import asyncio
import os
from dotenv import load_dotenv
import logging
import redis
from mariadb_connector import Alarm, update_alarm_to_db, get_alarm_from_db
from market_price import get_ton_usdt_price


load_dotenv()

# set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

THRESHOLD_PRICE = os.getenv("THRESHOLD_PRICE", 0.7)

redis_client = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)
toncenter = None


async def on_tick_success(watchmaker: str, base_asset_price: float, new_alarm_id: int):
    logger.info(f"Tick received: {watchmaker} {base_asset_price} {new_alarm_id}")
    new_price = await get_ton_usdt_price()
    if new_price is None:
        return
    new_price = round(new_price, 9)
    old_price = round(float(base_asset_price), 9)
    price_diff = abs(new_price - old_price)
    if price_diff > float(THRESHOLD_PRICE):
        need_asset_tup, alarm_info = await toncenter._estimate_wind(
            new_alarm_id, 1, new_price
        )
        need_base_asset = need_asset_tup[0]
        need_quote_asset = need_asset_tup[1]
        if new_price > old_price:
            max_buy_num = alarm_info["quote_asset_scale"]
        else:
            max_buy_num = alarm_info["base_asset_scale"]

        base_balance, quote_balance = await toncenter._get_user_balance()

        buy_num = await check_balance(
            base_balance,
            quote_balance,
            need_base_asset,
            need_quote_asset,
            max_buy_num,
        )
    if isinstance(buy_num, int):
        result = await toncenter.wind(
            alarm_id=new_alarm_id,
            buy_num=buy_num,
            new_price=new_price,
            skip_estimate=True,
            need_base_asset=need_base_asset,
            need_quote_asset=need_quote_asset,
        )
        logger.info(f"Wind result: {result}")


async def on_ring_success(alarm_id: int):
    logger.info(f"Ring received: alarm_id={alarm_id}")


async def on_wind_success(
    timekeeper: str, alarm_id: int, new_base_asset_price: float, new_alarm_id: int
):
    logger.info(
        f"Wind received: {timekeeper} {alarm_id} {new_base_asset_price} {new_alarm_id}"
    )


async def check_balance(
    base_bal: int,
    quote_bal: int,
    need_base: int,
    need_quote: int,
    max_buy_num: int,
):
    if base_bal < need_base:
        logger.error("Insufficient Base Asset Balance")
        return None
    if quote_bal < need_quote:
        logger.error("Insufficient Quote Asset Balance")
        return None
    if max_buy_num == 0:
        logger.error("Max Buy Num is 0")
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


async def main():
    global toncenter
    toncenter = await TicTonAsyncClient.init(testnet=True)

    await toncenter.subscribe(
        on_tick_success,
        on_ring_success,
        on_wind_success,
    )


if __name__ == "__main__":
    asyncio.run(main())
