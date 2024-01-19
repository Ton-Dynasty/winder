from tonsdk.utils import Address, to_nano
from tonsdk.boc import begin_cell
from tonsdk.contract.wallet import Wallets, WalletVersionEnum

from tonpy import CellSlice

from decimal import Decimal
from typing import Union
from dotenv import load_dotenv
import os
import time
import asyncio
import json

from utils import float_conversion, int_conversion, to_token
from ton_center_client import TonCenterTonClient
from mariadb_connector import get_alarm_from_db, update_alarm_to_db

load_dotenv()

QUOTEASSET_DECIMALS = 6
BASEASSET_DECIMALS = 9
GAS_FEE = to_nano(1, "ton")
API_KEY = os.getenv("TEST_TONCENTER_API_KEY")

ORACLE = Address("kQCFEtu7e-su_IvERBf4FwEXvHISf99lnYuujdo0xYabZQgW")

MNEMONICS, PUB_K, PRIV_K, WALLET = Wallets.from_mnemonics(
    mnemonics=str(os.getenv("MNEMONICS")).split(" "),
    version=WalletVersionEnum.v4r2,
    workchain=0,
)


def to_usdt(amount: Union[int, float, str, Decimal]) -> Decimal:
    return to_token(amount, QUOTEASSET_DECIMALS)


def to_ton(amount: Union[int, float, str, Decimal]) -> Decimal:
    return to_token(amount, BASEASSET_DECIMALS)


def to_bigint(amount: Union[int, float, str, Decimal]) -> int:
    return int(Decimal(amount).to_integral_value())


"""Get Method"""


async def get_total_amount():
    client = TonCenterTonClient(API_KEY)
    result = await client.run_get_method(ORACLE.to_string(), "TotalAmount", [])
    return int(result, 16)


async def get_alarm_info(alarm_address: str):
    client = TonCenterTonClient(API_KEY)
    get_methods = [
        "getBaseAssetScale",
        "getQuoteAssetScale",
        "getRemainScale",
        "getBaseAssetPrice",
    ]
    tasks = [client.run_get_method(alarm_address, method, []) for method in get_methods]
    results = await asyncio.gather(*tasks)
    base_asset_scale, quote_asset_scale, remain_scale, base_asset_price = [
        int(result, 16) for result in results
    ]
    return {
        "base_asset_scale": base_asset_scale,
        "quote_asset_scale": quote_asset_scale,
        "remain_scale": remain_scale,
        "base_asset_price": base_asset_price,
    }


async def get_address_balance(address: str):
    client = TonCenterTonClient(API_KEY)
    result = await client.get_address_balance(address)

    return result


async def get_token_balance(address: str):
    client = TonCenterTonClient(API_KEY)
    result = await client.get_token_data(address)
    return result["balance"]


async def check_alarms(alarm_id_list: list):
    client = TonCenterTonClient(API_KEY)

    # get alarm dict
    alarm_dict = await get_alarm_from_db()
    if alarm_dict is None:
        return []

    # get alarm address bytes
    tasks = [
        client.run_get_method(
            ORACLE.to_string(), "getAlarmAddress", [["num", alarm_id]]
        )
        for alarm_id in alarm_id_list
    ]
    results = await asyncio.gather(*tasks)
    address_bytes_list = [result["bytes"] for result in results]

    # get alarm address
    address_list = []
    for alarm_id, address_bytes in zip(alarm_id_list, address_bytes_list):
        alarm_info = alarm_dict.get(str(alarm_id))
        if alarm_info and alarm_info.get("address"):
            address_list.append(alarm_info["address"])
        else:
            # TODO: Maybe someday we can use this
            # cell_bytes = base64.b64decode(result[0][1]["bytes"])
            cs = CellSlice(address_bytes)
            address = cs.load_address()
            alarm_dict[str(alarm_id)] = {"address": address}
            address_list.append(address)

    # get alarm state
    tasks = [client.get_address_state(address) for address in address_list]
    alarm_state_list = await asyncio.gather(*tasks)

    # update alarm dict
    for alarm_id, alarm_state in zip(alarm_id_list, alarm_state_list):
        alarm_dict[str(alarm_id)]["state"] = alarm_state

    result = []
    for alarm_id in alarm_id_list:
        alarm_info = alarm_dict[str(alarm_id)]
        if alarm_info["state"] == "active":
            result.append((alarm_id, alarm_info["address"]))

    # update alarm dict to db
    await update_alarm_to_db(alarm_dict)

    return result


"""Tick, Wind, Ring"""


async def tick(
    watchmaker,
    oracle,
    quote_asset_to_transfer,
    base_asset_to_transfer=1,
    expire_at=int(time.time()) + 1000,
    extra_fees=2,
):
    base_asset_price = float_conversion(to_usdt(quote_asset_to_transfer)) // to_ton(
        base_asset_to_transfer
    )
    quote_asset_transfered = to_usdt(quote_asset_to_transfer)
    forward_ton_amount = float_conversion(
        quote_asset_transfered
    ) / base_asset_price + to_ton(extra_fees)
    forward_info = (
        begin_cell()
        .store_uint(0, 8)
        .store_uint(expire_at, 256)
        .store_uint(to_bigint(base_asset_price), 256)
        .end_cell()
    )

    client = TonCenterTonClient(API_KEY)
    seqno = await client.run_get_method(watchmaker.address.to_string(), "seqno", [])

    body = (
        begin_cell()
        .store_uint(0xF8A7EA5, 32)
        .store_uint(0, 64)
        .store_coins(to_bigint(quote_asset_transfered))
        .store_address(oracle)
        .store_address(watchmaker.address)
        .store_bit(False)
        .store_coins(to_bigint(forward_ton_amount))
        .store_ref(forward_info)
        .end_cell()
    )

    query = watchmaker.create_transfer_message(
        to_addr="kQCQ1B7B7-CrvxjsqgYT90s7weLV-IJB2w08DBslDdrIXucv",
        amount=to_nano(4, "ton"),
        seqno=int(seqno, 16),
        payload=body,
    )
    boc = query["message"].to_boc(False)

    tasks = [get_total_amount(), client.send_boc(boc)]
    results = await asyncio.gather(*tasks)

    alarm_id = results[0]
    tick_result = results[1]

    return tick_result, alarm_id


async def wind(
    timekeeper, oracle, alarm_id, buy_num, new_price, need_quoate_asset, need_base_asset
):
    client = TonCenterTonClient(API_KEY)
    seqno = await client.run_get_method(timekeeper.address.to_string(), "seqno", [])
    forward_info = (
        begin_cell()
        .store_uint(1, 8)
        .store_uint(alarm_id, 256)
        .store_uint(buy_num, 32)
        .store_uint(to_bigint(new_price), 256)
        .end_cell()
    )

    body = (
        begin_cell()
        .store_uint(0xF8A7EA5, 32)
        .store_uint(0, 64)
        .store_coins(to_bigint(need_quoate_asset))
        .store_address(oracle)
        .store_address(timekeeper.address)
        .store_bit(False)
        .store_coins(to_bigint(need_base_asset))
        .store_ref(forward_info)
        .end_cell()
    )
    query = timekeeper.create_transfer_message(
        to_addr="kQCQ1B7B7-CrvxjsqgYT90s7weLV-IJB2w08DBslDdrIXucv",
        amount=to_bigint(need_base_asset) + GAS_FEE,
        seqno=int(seqno, 16),
        payload=body,
    )

    boc = query["message"].to_boc(False)
    tasks = [get_total_amount(), client.send_boc(boc)]
    results = await asyncio.gather(*tasks)

    alarm_id = results[0]
    wind_result = results[1]

    if wind_result["@type"] == "ok":
        update_alarm_dict = {
            str(alarm_id): {
                "address": "is Mine",
                "state": "active",
                "price": to_bigint(new_price),
            }
        }
        await update_alarm_to_db(update_alarm_dict)

    return wind_result, alarm_id


async def ring(
    watchmaker,
    oracle,
    alarm_id,
):
    client = TonCenterTonClient(API_KEY)
    seqno = await client.run_get_method(watchmaker.address.to_string(), "seqno", [])
    body = (
        begin_cell()
        .store_uint(0xC3510A29, 32)
        .store_uint(0, 257)
        .store_uint(alarm_id, 257)
        .end_cell()
    )
    query = watchmaker.create_transfer_message(
        to_addr=oracle.to_string(),
        amount=to_nano(1, "ton"),
        seqno=int(seqno, 16),
        payload=body,
    )
    boc = query["message"].to_boc(False)

    update_alarm_dict = {
        str(alarm_id): {"address": "is Mine", "state": "uninitialied", "price": 0}
    }

    await update_alarm_to_db(update_alarm_dict)

    return await client.send_boc(boc)


async def main():
    # print(
    #     await tick(
    #         watchmaker=WALLET,
    #         oracle=ORACLE,
    #         quote_asset_to_transfer=2,
    #         base_asset_to_transfer=1,
    #     )
    # )
    print(await ring(WALLET, ORACLE, 10))
    # print(
    #     await wind(
    #         timekeeper=WALLET,
    #         oracle=ORACLE,
    #         alarm_id=3,
    #         buy_num=1,
    #         new_price=92233720368547758,
    #         need_quoate_asset=11999999,
    #         need_base_asset=2000000000,
    #     )
    # )
    # print(await get_total_amount())
    # print(await check_alarms([1]))
    # print(await get_alarm_info("EQAWIJ3mBo990Ui8kinaodH3AlMi6Q3aPuhUNoFySO08uhEP"))


if __name__ == "__main__":
    asyncio.run(main())
