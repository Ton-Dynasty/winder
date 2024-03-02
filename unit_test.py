import asyncio
import os
from dotenv import load_dotenv
from ticton import FixedFloat, to_token, TicTonAsyncClient

load_dotenv()


async def init_test():
    client = await TicTonAsyncClient.init(
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


async def subscribe_test():
    client = await init_test()
    await client.subscribe()


async def main():
    await init_test()
    # await tick_test()
    # await wind_test(22)
    # await ring_test(1)
    # await subscribe_test()


if __name__ == "__main__":
    asyncio.run(main())
