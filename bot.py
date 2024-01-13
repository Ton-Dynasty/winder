import asyncio
import json
import os
from dotenv import load_dotenv

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
from market_price import ton_usdt_prices_generator

load_dotenv()

THRESHOLD_PRICE = float_conversion(1) * to_usdt(1) // to_ton(1)
MIN_BASEASSET_THRESHOLD = to_ton(1)
EXTRA_FEES = to_ton(1)
ORACLE = Address("kQCFEtu7e-su_IvERBf4FwEXvHISf99lnYuujdo0xYabZQgW")

MNEMONICS, PUB_K, PRIV_K, WALLET = Wallets.from_mnemonics(
    mnemonics=str(os.getenv("MNEMONICS")).split(" "),
    version=WalletVersionEnum.v4r2,
    workchain=0,
)
QUOTE_JETTON_WALLET = Address("kQCQ1B7B7-CrvxjsqgYT90s7weLV-IJB2w08DBslDdrIXucv")
PATH_TO_ALARM_JSON = "data/alarm.json"


async def load_alarms():
    with open(PATH_TO_ALARM_JSON, "r") as file:
        return json.load(file)


async def save_alarms(updated_alarms):
    with open(PATH_TO_ALARM_JSON, "w") as file:
        json.dump(updated_alarms, file, indent=4)


async def find_active_alarm():
    alarms = await load_alarms()
    total_alarms = await get_total_amount()

    # Determine if there are new alarms and which are active
    alarms_to_check = []
    for i in range(total_alarms):
        str_i = str(i)
        if str_i not in alarms or (
            alarms[str_i]["address"] != "is Mine" and alarms[str_i]["state"] == "active"
        ):
            alarms_to_check.append(str_i)
    print("alarms: ", alarms_to_check)
    # Check alarms and get active alarms [(id, address)]
    active_alarms = await check_alarms(alarms_to_check)

    return active_alarms


async def estimate(alarm: tuple, price: float, base_bal, quote_bal):
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
    if base_bal < need_base:
        print("Insufficient base asset balance")
        return None
    if quote_bal < need_quote:
        print("Insufficient quote asset balance")
        return None
    if max_buy_num == 0:
        print("Max buy num is 0")
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
            print("Alarm", alarm[0], "finished")

        print("Alarm", alarm[0], "no need to wind")


async def tick_one_scale(price, base_bal, quote_bal):
    if to_bigint(base_bal) < to_ton(3):
        print("Insufficient base asset balance")
        return None
    if to_bigint(quote_bal) < to_usdt(price):
        print("Insufficient quote asset balance")
        return None
    tick_result, alarm_id = await tick(
        watchmaker=WALLET,
        oracle=ORACLE,
        quote_asset_to_transfer=price,
        base_asset_to_transfer=1,
    )
    print("Tick result:", tick_result)
    print("Alarm id:", alarm_id)

    if tick_result["@type"] == "ok":
        alarm_dict = await load_alarms()
        alarm_dict[str(alarm_id)] = {
            "address": "is Mine",
            "state": "active",
            "price": price,
        }
        await save_alarms(alarm_dict)


async def main():
    price_generator = ton_usdt_prices_generator()
    async for price in price_generator:
        print("Price:", price)
        base_bal = await get_address_balance(WALLET.address.to_string())
        quote_bal = await get_token_balance(QUOTE_JETTON_WALLET.to_string())
        active_alarms = await find_active_alarm()
        print("Active alarms:", active_alarms)
        if active_alarms == []:
            print("No active alarms, then tick")
            await tick_one_scale(price, base_bal, quote_bal)

        await wind_alarms(active_alarms, price, base_bal, quote_bal)


if __name__ == "__main__":
    asyncio.run(main())
