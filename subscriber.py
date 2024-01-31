from sdk import TicTonAsyncClient
import asyncio
import os
from dotenv import load_dotenv
import logging
import redis
from mariadb_connector import update_alarm_to_db
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

redis_client = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)


async def on_tick_success(watchmaker: str, base_asset_price: int):
    print(f"Tick received: {watchmaker} {base_asset_price}")


async def on_ring_success(alarm_id: int):
    print(f"Ring received: alarm_id={alarm_id}")


async def on_wind_success(timekeeper: str, alarm_id: int, new_base_asset_price: int):
    print(f"Wind received: {timekeeper} {alarm_id} {new_base_asset_price}")


async def find_active_alarm():
    client = await TicTonAsyncClient.init()
    total_alarms = await client.get_alarms_amount()

    # Get last 20 alarms
    if total_alarms < 20:
        alarms_to_check = [i for i in range(total_alarms)]
    else:
        alarms_to_check = [i for i in range(total_alarms - 20, total_alarms)]
    logger.info(f"Alarms to Check: {alarms_to_check}")
    # Check alarms and get active alarms [(id, address)]
    alarm_dict = await client.check_alarms(alarms_to_check)
    print(alarm_dict)

    return None


async def initialize():
    try:
        # price = await get_ton_usdt_price()
        price = 2.2
        if price is not None:
            price = round(float(price), 9)
            logger.info("========== New Price Get ===========")
            logger.info(f"New Price: {price}")
            active_alarms = await find_active_alarm()

    except Exception as e:
        logger.error(f"Error while running bot {e}")


async def main():
    client = await TicTonAsyncClient.init(
        mnemonics=os.getenv("MNEMONICS"),
        oracle_addr=os.getenv("ORACLE_ADDRESS"),
        toncenter_api_key=os.getenv("TEST_TONCENTER_API_KEY"),
        testnet=True,
    )
    await initialize()

    await client.subscribe(on_tick_success, on_ring_success, on_wind_success)


if __name__ == "__main__":
    asyncio.run(main())
