from sdk import TicTonAsyncClient, FixedFloat
import asyncio
import os
from dotenv import load_dotenv
import logging
import redis
from mariadb_connector import Alarm, update_alarm_to_db, get_alarm_from_db
from market_price import get_ton_usdt_price

from tonsdk.utils import Address


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

MY_ADDRESS = Address(os.getenv("MY_ADDRESS")).to_string(False)
print(MY_ADDRESS)


async def on_tick_success(watchmaker: str, base_asset_price: float, new_alarm_id: int):
    logger.info(f"Tick received: {watchmaker} {base_asset_price} {new_alarm_id}")
    price = round(float(base_asset_price), 9)
    watchmaker = Address(watchmaker).to_string(False)
    is_mine = watchmaker == MY_ADDRESS
    alarm = Alarm(id=new_alarm_id, price=price, is_mine=is_mine)
    await update_alarm_to_db([alarm])


async def on_ring_success(alarm_id: int):
    logger.info(f"Ring received: alarm_id={alarm_id}")
    alarm = Alarm(id=alarm_id, state="uninitialized")
    alarm = await update_alarm_to_db([alarm])


async def on_wind_success(
    timekeeper: str,
    alarm_id: int,
    new_base_asset_price: float,
    remain_scale: int,
    new_alarm_id: int,
):
    logger.info(
        f"Wind received: {timekeeper} {alarm_id} {new_base_asset_price} {new_alarm_id} {remain_scale}"
    )
    price = round(float(new_base_asset_price), 9)
    timekeeper = Address(timekeeper).to_string(False)
    is_mine = timekeeper == MY_ADDRESS
    alarm = Alarm(id=alarm_id, remain_scale=remain_scale)
    new_alarm = Alarm(id=new_alarm_id, price=price, is_mine=is_mine)
    await update_alarm_to_db([alarm, new_alarm])


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
