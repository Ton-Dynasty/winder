from tonsdk.utils import Address, to_nano
from tonsdk.boc import Cell, begin_cell
from tonsdk.provider import ToncenterClient, prepare_address
from tonsdk.contract.wallet import Wallets, WalletVersionEnum
import base64

from decimal import Decimal
from typing import Union
from dotenv import load_dotenv
import os
import time
import asyncio
import aiohttp

from utils import float_conversion, int_conversion, to_token

load_dotenv()

QUOTEASSET_DECIMALS = 6
BASEASSET_DECIMALS = 9
GASS_FEE = to_nano(1, "ton")
MIN_BASEASSET_THRESHOLD = to_nano(1, "ton")
REWARD_JETTON_CONTENT = begin_cell().end_cell()
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


class TonCenterTonClient:
    def __init__(self, api_key):
        self.provider = ToncenterClient(
            base_url="https://testnet.toncenter.com/api/v2/",
            api_key=api_key,
        )

    async def run_get_method(self, addr: str, method: str, stack: list):
        addr = prepare_address(addr)
        result = await self._run(self.provider.raw_run_method(addr, method, stack))

        if result.get("@type") == "smc.runResult" and "stack" in result:
            result = result["stack"]

        return result

    async def send_boc(self, boc):
        return await self._run(self.provider.raw_send_message(boc))

    async def _run(self, to_run):
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            func = to_run["func"]
            args = to_run["args"]
            kwargs = to_run["kwargs"]
            return await func(session, *args, **kwargs)


async def get_total_amount():
    client = TonCenterTonClient(API_KEY)
    result = await client.run_get_method(ORACLE.to_string(), "TotalAmount", [])
    return result[0][1]


async def get_alarm_address(alarm_id: int):
    client = TonCenterTonClient(API_KEY)
    result = await client.run_get_method(
        ORACLE.to_string(), "getAlarmAddress", [["num", alarm_id]]
    )
    # TODO: Maybe someday we can use this
    # cell_bytes = base64.b64decode(result[0][1]["bytes"])
    from tonpy import CellSlice
    cs = CellSlice(result[0][1]["bytes"])
    return cs.load_address()


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
    seqno = await client.run_get_method(watchmaker.to_string(), "seqno", [])
    # print("watchmaker", watchmaker.to_string())
    # print("oracle", oracle.to_string())
    # print("base_asset_price", base_asset_price)
    # print("quote_asset_transfered", to_bigint(quote_asset_transfered))
    # print("forward_ton_amount", to_bigint(forward_ton_amount))

    body = (
        begin_cell()
        .store_uint(0xF8A7EA5, 32)
        .store_uint(0, 64)
        .store_coins(to_bigint(quote_asset_transfered))
        .store_address(oracle)
        .store_address(watchmaker)
        .store_bit(False)
        .store_coins(to_bigint(forward_ton_amount))
        .store_ref(forward_info)
        .end_cell()
    )

    query = watchmaker.create_transfer_message(
        to_addr="kQCQ1B7B7-CrvxjsqgYT90s7weLV-IJB2w08DBslDdrIXucv",
        amount=to_nano(4, "ton"),
        seqno=int(seqno[0][1], 16),
        payload=body,
    )
    boc = query["message"].to_boc(False)

    tasks = [get_total_amount(), client.send_boc(boc)]
    results = await asyncio.gather(*tasks)

    alarm_id = int(results[0], 16) + 1
    tick_result = results[1]

    return tick_result, alarm_id


async def tock():
    pass


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
    print(oracle.to_string())
    query = watchmaker.create_transfer_message(
        to_addr=oracle.to_string(),
        amount=to_nano(1, "ton"),
        seqno=int(seqno[0][1], 16),
        payload=body,
    )
    boc = query["message"].to_boc(False)
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
    # result = await ring(watchmaker=WALLET, oracle=ORACLE, alarm_id=0)
    # print(result)
    # print(await get_total_amount())
    print(await get_alarm_address(0))


if __name__ == "__main__":
    asyncio.run(main())
