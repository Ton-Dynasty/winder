from sdk import TicTonAsyncClient
import asyncio
import os
from dotenv import load_dotenv

load_dotenv()


async def on_tick_success(watchmaker: str, base_asset_price: int):
    print(f"Tick received: {watchmaker} {base_asset_price}")


async def on_ring_success(alarm_id: int):
    print(f"Ring received: alarm_id={alarm_id}")


async def on_wind_success(timekeeper: str, alarm_id: int, new_base_asset_price: int):
    print(f"Wind received: {timekeeper} {alarm_id} {new_base_asset_price}")


async def main():
    client = await TicTonAsyncClient.init(
        mnemonics=os.getenv("MNEMONICS"),
        oracle_addr=os.getenv("ORACLE_ADDRESS"),
        toncenter_api_key=os.getenv("TEST_TONCENTER_API_KEY"),
        testnet=True,
    )

    await client.subscribe(on_tick_success, on_ring_success, on_wind_success)


if __name__ == "__main__":
    asyncio.run(main())
