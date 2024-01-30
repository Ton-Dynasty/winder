import asyncio
import os
from dotenv import load_dotenv
from sdk import FixedFloat, to_token, TicTonAsyncClient

load_dotenv()


async def init_test():
    client = await TicTonAsyncClient.init(
        mnemonics=os.getenv("MNEMONICS"),
        oracle_addr=os.getenv("ORACLE_ADDRESS"),
        toncenter_api_key=os.getenv("TEST_TONCENTER_API_KEY"),
        testnet=True,
    )
    # print(client.metadata)

    return client


async def tick_test():
    client = await init_test()
    tick = await client.tick(4.0)
    print(tick)


async def ring_test(alarm_id):
    client = await init_test()
    ring = await client.ring(alarm_id)
    print(ring)


async def wind_test(alram_id):
    client = await init_test()
    wind = await client.wind(alram_id, 1, 5.0)
    print(wind)


async def main():
    # await init_test()
    # await tick_test()
    # await wind_test(12)
    await ring_test(14)


if __name__ == "__main__":
    asyncio.run(main())
