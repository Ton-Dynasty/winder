import ccxt
import numpy as np
import time

# here is a list of exchanges that dont require KYC and have TON/USDT pair
EXCHANGE_LIST = [
    "bigone",
    "bitfinex",
    "bitfinex2",
    "bitmart",
    "bitopro",
    "bitrue",
    "bybit",
    "coinex",
    "digifinex",
    "exmo",
    "gate",
    "gateio",
    "htx",
    "huobi",
    "kucoin",
    "lbank",
    "mexc",
    "okx",
    "poloniex",
]


def fetch_ton_usdt_prices():
    while True:  # infinite loop
        prices = []
        # time starts
        start_time = time.time()
        for exchange_id in EXCHANGE_LIST:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class()
            try:
                markets = exchange.load_markets()
                if "TON/USDT" in markets:
                    price = exchange.fetch_ticker("TON/USDT")["last"]
                    prices.append(price)
            except Exception as e:
                print(f"Error fetching from {exchange_id}: {str(e)}")

        # time ends
        end_time = time.time()

        if prices:
            median_price = np.median(prices)
            print(f"Time taken: {end_time - start_time} seconds")
            yield median_price  # Use yield instead of return
        else:
            yield None


if __name__ == "__main__":
    price_generator = fetch_ton_usdt_prices()
    for current_median_price in price_generator:
        if current_median_price is not None:
            print(f"Current median price of TON/USDT: {current_median_price}")
        else:
            print("No prices fetched.")
