import ccxt.async_support as ccxt
import asyncio
import os
import redis
from dotenv import load_dotenv

from log_config import setup_logging
import logging

setup_logging()

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

EXCHANGE_LIST = [
    "bybit",
    "gateio",
    "okx",
]

redis_client = redis.StrictRedis(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
)


async def fetch_price_from_exchange(exchange_id, symbol="TON/USDT"):
    try:
        exchange_class = getattr(ccxt, exchange_id)
        async with exchange_class() as exchange:
            await exchange.load_markets()
            if symbol in exchange.markets:
                ticker = await exchange.fetch_ticker(symbol)
                return ticker["last"]
    except Exception as e:
        logging.error(f"Error while fetching price from {exchange_id}", e)
        return None


async def fetch_ton_usdt_prices():
    tasks = [fetch_price_from_exchange(exchange) for exchange in EXCHANGE_LIST]
    prices = await asyncio.gather(*tasks)
    return [price for price in prices if price is not None]


async def set_ton_usdt_prices():
    while True:
        prices = await fetch_ton_usdt_prices()
        if prices:
            price = sum(prices) / len(prices)
            redis_client.set("ton_usdt_price", price)
        else:
            continue


async def get_ton_usdt_price():
    return redis_client.get("ton_usdt_price")


if __name__ == "__main__":
    asyncio.run(set_ton_usdt_prices())
