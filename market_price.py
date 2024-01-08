import ccxt.async_support as ccxt
import numpy as np
import time
import asyncio

EXCHANGE_LIST = [
    "bybit",
    "gateio",
    "okx",
]


async def fetch_price_from_exchange(exchange_id, symbol="TON/USDT"):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        async with exchange_class() as exchange:
            await exchange.load_markets()
            if symbol in exchange.markets:
                ticker = await exchange.fetch_ticker(symbol)
                return ticker["last"]
    except Exception as e:
        print(f"Error fetching from {exchange_id}: {str(e)}")
        return None


async def fetch_ton_usdt_prices():
    tasks = [fetch_price_from_exchange(exchange) for exchange in EXCHANGE_LIST]
    prices = await asyncio.gather(*tasks)
    return [price for price in prices if price is not None]


def generator_ton_usdt_prices():
    while True:
        start_time = time.time()
        prices = asyncio.run(fetch_ton_usdt_prices())
        end_time = time.time()
        print(f"Time taken: {end_time - start_time} seconds")
        if prices:
            yield np.mean(prices)
        else:
            yield None


if __name__ == "__main__":
    prices = generator_ton_usdt_prices()
    for _ in range(10):
        print(next(prices))
