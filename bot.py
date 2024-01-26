import asyncio
import os
from dotenv import load_dotenv
import logging


from tonsdk.utils import Address
from tonsdk.contract.wallet import Wallets, WalletVersionEnum

from oracle_interface import tick, wind, ring
from oracle_interface import (
    get_total_amount,
    get_alarm_info,
    check_alarms,
    get_address_balance,
    get_token_balance,
)
from oracle_interface import to_usdt, to_ton, to_bigint
from utils import float_conversion, int_conversion
from market_price import get_ton_usdt_price
from mariadb_connector import get_alarm_from_db, update_alarm_to_db

load_dotenv()

# set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

THRESHOLD_PRICE = (
    float_conversion(os.getenv("THRESHOLD_PRICE")) * to_usdt(1) // to_ton(1)
)
MIN_BASEASSET_THRESHOLD = to_ton(1)
EXTRA_FEES = to_ton(1)
ORACLE = Address(os.getenv("ORACLE_ADDRESS"))

MNEMONICS, PUB_K, PRIV_K, WALLET = Wallets.from_mnemonics(
    mnemonics=str(os.getenv("MNEMONICS")).split(" "),
    version=WalletVersionEnum.v4r2,
    workchain=0,
)
QUOTE_JETTON_WALLET = Address(os.getenv(("QUOTE_JETTON_WALLET_ADDRESS")))


async def load_alarms():
    return await get_alarm_from_db()


async def save_alarms(updated_alarms):
    await update_alarm_to_db(updated_alarms)


async def find_active_alarm():
    alarms = await load_alarms()
    total_alarms = await get_total_amount()

    if alarms is None:
        return []

    # Determine if there are new alarms and which are active
    alarms_to_check = []
    for i in range(total_alarms):
        if i not in alarms or (
            alarms[i]["address"] != "is Mine" and alarms[i]["state"] == "active"
        ):
            alarms_to_check.append(i)
    logger.info(f"Alarms to Check: {alarms_to_check}")
    # Check alarms and get active alarms [(id, address)]
    active_alarms = await check_alarms(alarms_to_check)

    return active_alarms


async def estimate(alarm: tuple, price: float, base_bal, quote_bal):
    logger.info(f"Estimate Alarm {alarm[0]}")
    alarm_info = await get_alarm_info(alarm[1])  # alarm[1] is address
    new_price = float_conversion(price) * to_usdt(1) // to_ton(1)
    old_price = alarm_info["base_asset_price"]
    price_delta = abs(new_price - old_price)

    if price_delta < THRESHOLD_PRICE:
        return None

    if new_price > old_price:
        # Timekeeper will pay quote asset and buy base asset
        need_quote_asset = int_conversion(
            new_price * 2 * MIN_BASEASSET_THRESHOLD
            + old_price * MIN_BASEASSET_THRESHOLD
        )
        need_base_asset = MIN_BASEASSET_THRESHOLD + EXTRA_FEES
        max_buy_num = alarm_info["base_asset_scale"]
    else:
        # Timekeeper will pay base asset and buy quote asset
        need_quote_asset = int_conversion(
            new_price * 2 * MIN_BASEASSET_THRESHOLD
            - old_price * MIN_BASEASSET_THRESHOLD
        )
        need_base_asset = MIN_BASEASSET_THRESHOLD * 3 + EXTRA_FEES
        max_buy_num = alarm_info["quote_asset_scale"]

    buy_num = await check_balance(
        to_bigint(base_bal),
        to_bigint(quote_bal),
        to_bigint(need_base_asset),
        to_bigint(need_quote_asset),
        max_buy_num,
    )
    if buy_num is None:
        return None

    return {
        "alarm_id": alarm[0],
        "new_price": new_price,
        "need_quote_asset": to_bigint(max(0, need_quote_asset)),
        "need_base_asset": to_bigint(max(0, need_base_asset)),
        "buy_num": buy_num,
    }


async def check_balance(
    base_bal: int,
    quote_bal: int,
    need_base: int,
    need_quote: int,
    max_buy_num: int,
):
    logger.info("Check Balance")
    if base_bal < need_base:
        logger.info("Insufficient Base Asset Balance")
        return None
    if quote_bal < need_quote:
        logger.info("Insufficient Quote Asset Balance")
        return None
    if max_buy_num == 0:
        logger.info("Max Buy Num is 0")
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


async def wind_alarms(active_alarms, price, base_bal, quote_bal):
    if active_alarms == []:
        return
    for alarm in active_alarms:
        alarm_info = await estimate(alarm, price, base_bal, quote_bal)
        if alarm_info:
            await wind(
                timekeeper=WALLET,
                oracle=ORACLE,
                alarm_id=int(alarm_info["alarm_id"]),
                buy_num=alarm_info["buy_num"],
                new_price=alarm_info["new_price"],
                need_quoate_asset=alarm_info["need_quote_asset"],
                need_base_asset=alarm_info["need_base_asset"],
            )
            base_bal -= alarm_info["need_base_asset"]
            quote_bal -= alarm_info["need_quote_asset"]
            logger.info(f"Alarm {alarm[0]} Wind Successfully")

        else:
            logger.info(f"Alarm {alarm[0]} No Need to Wind")


async def tick_one_scale(price, base_bal, quote_bal):
    pass  # In V0, we don't need to tick when there is no active alarms
    # if to_bigint(base_bal) < to_ton(3):
    #     print("Insufficient base asset balance")
    #     return None
    # if to_bigint(quote_bal) < to_usdt(price):
    #     print("Insufficient quote asset balance")
    #     return None
    # tick_result, alarm_id = await tick(
    #     watchmaker=WALLET,
    #     oracle=ORACLE,
    #     quote_asset_to_transfer=price,
    #     base_asset_to_transfer=1,
    # )
    # print("Tick result:", tick_result)
    # print("Alarm id:", alarm_id)
    #
    # if tick_result["@type"] == "ok":
    #     alarm_dict = await load_alarms()
    #     alarm_dict[str(alarm_id)] = {
    #         "address": "is Mine",
    #         "state": "active",
    #         "price": price,
    #     }
    #     await save_alarms(alarm_dict)


async def main():
    while True:
        try:
            price = await get_ton_usdt_price()
            if price is None:
                continue
            price = round(float(price), 9)
            # =========== New Price Get ===========
            logger.info("========== New Price Get ===========")
            logger.info(f"New Price: {price}")
            base_bal = int(await get_address_balance(WALLET.address.to_string()))
            quote_bal = int(await get_token_balance(QUOTE_JETTON_WALLET.to_string()))
            active_alarms = await find_active_alarm()
            logger.info(f"Active Alarms: {active_alarms}")
            if active_alarms == []:
                logging.info("No Active Alarms")
                await tick_one_scale(price, base_bal, quote_bal)

            await wind_alarms(active_alarms, price, base_bal, quote_bal)

        except Exception as e:
            logger.error(f"Error while running bot {e}")
            continue


if __name__ == "__main__":
    asyncio.run(main())
