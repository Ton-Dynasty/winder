from ticton import TicTonAsyncClient
from ticton.callbacks import (
    OnTickSuccessParams,
    OnRingSuccessParams,
    OnWindSuccessParams,
)
import asyncio
import os
from dotenv import load_dotenv
import logging
import redis
from mariadb_connector import Alarm, update_alarm_to_db

from tonsdk.utils import Address
from pytoncenter.address import Address as PyAddress


load_dotenv()

# set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

THRESHOLD_PRICE = os.getenv("THRESHOLD_PRICE", 0.7)

redis_client = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)

MY_ADDRESS = PyAddress(os.getenv("MY_ADDRESS", "")).to_string(False)


async def on_tick_success(on_tick_success_params: OnTickSuccessParams):
    logger.info(f"Tick received: {on_tick_success_params}")
    price = round(float(on_tick_success_params.base_asset_price), 9)
    watchmaker = PyAddress(on_tick_success_params.watchmaker).to_string(False)
    is_mine = watchmaker == MY_ADDRESS
    alarm = Alarm(
        id=on_tick_success_params.new_alarm_id,
        price=price,
        is_mine=is_mine,
        created_at=on_tick_success_params.created_at,
    )
    await update_alarm_to_db([alarm])


async def on_ring_success(on_ring_success_params: OnRingSuccessParams):
    logger.info(f"Ring received: {on_ring_success_params}")
    alarm = Alarm(id=on_ring_success_params.alarm_id, state="uninitialized")
    await update_alarm_to_db([alarm])


async def on_wind_success(on_wind_success_params: OnWindSuccessParams):
    logger.info(f"Wind received: {on_wind_success_params}")
    price = round(float(on_wind_success_params.new_base_asset_price), 9)
    timekeeper = PyAddress(on_wind_success_params.timekeeper).to_string(False)
    is_mine = timekeeper == MY_ADDRESS
    alarm = Alarm(
        id=on_wind_success_params.alarm_id,
        remain_scale=on_wind_success_params.remain_scale,
    )
    new_alarm = Alarm(
        id=on_wind_success_params.new_alarm_id,
        price=price,
        is_mine=is_mine,
        created_at=on_wind_success_params.created_at,
    )
    await update_alarm_to_db([alarm, new_alarm])


async def subscribe():
    client = await TicTonAsyncClient.init(testnet=True)

    await client.subscribe(
        on_tick_success=on_tick_success,
        on_wind_success=on_wind_success,
        on_ring_success=on_ring_success,
        start_lt="latest",
    )


if __name__ == "__main__":
    asyncio.run(subscribe())
