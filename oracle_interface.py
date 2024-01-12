from bitarray import bits2bytes
from tonsdk.utils import Address, concat_bytes, to_nano, bytes_to_b64str
from tonsdk.boc import Cell, begin_cell, deserialize_cell_data
from tonsdk.provider import ToncenterClient, prepare_address, address_state
from tonsdk.contract.token.ft import JettonWallet
from tonsdk.contract.wallet import Wallets, WalletVersionEnum


from decimal import Decimal
from typing import Union
import requests
from dotenv import load_dotenv
import os
import json
import time
from abc import ABC, abstractmethod
import asyncio
import aiohttp
from tvm_valuetypes import serialize_tvm_stack

from utils import float_conversion, int_conversion, to_token

load_dotenv()

QUOTEASSET_DECIMALS = 6
BASEASSET_DECIMALS = 9
GASS_FEE = to_nano(1, "ton")
MIN_BASEASSET_THRESHOLD = to_nano(1, "ton")
REWARD_JETTON_CONTENT = begin_cell().end_cell()
API_KEY = os.getenv("TEST_TONCENTER_API_KEY")
ORACLE_ADDRESS = Address("kQCFEtu7e-su_IvERBf4FwEXvHISf99lnYuujdo0xYabZQgW")

MNEMONICS, PUB_K, PRIV_K, WALLET = Wallets.from_mnemonics(
    mnemonics=os.getenv("MNEMONICS").split(" "),
    version=WalletVersionEnum.v4r2,
    workchain=0,
)
JETTON_WALLET_ADDRESS = Address("0QApdUMEOUuHnBo-RSdbikkZZ3qWItZLdXjyff9lN_eS5Zib")


def to_usdt(amount: Union[int, float, str, Decimal]) -> Decimal:
    return to_token(amount, QUOTEASSET_DECIMALS)


def to_ton(amount: Union[int, float, str, Decimal]) -> Decimal:
    return to_token(amount, BASEASSET_DECIMALS)


def to_bigint(amount: Union[int, float, str, Decimal]) -> int:
    return int(Decimal(amount).to_integral_value())


class TonCenterTonClient:
    def __init__(self):
        try:
            self.loop = asyncio.get_event_loop()

        except RuntimeError:  # This is raised when there is no current event loop
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)

        self.provider = ToncenterClient(
            base_url="https://testnet.toncenter.com/api/v2/",
            api_key=API_KEY,
        )

    def run_get_method(self, addr: str, methood: str, stack: list):
        addr = prepare_address(addr)
        result = self._run(self.provider.raw_run_method(addr, methood, stack))

        if result[0].get("@type") == "smc.runResult" and "stack" in result[0]:
            result = result[0]["stack"]

        return result

    def send_boc(self, boc):
        return self._run(self.provider.raw_send_message(boc))

    def _run(self, to_run, *, single_query=True):
        try:
            return self.loop.run_until_complete(self._execute(to_run, single_query))

        except Exception:
            raise

    async def _execute(self, to_run, single_query):
        timeout = aiohttp.ClientTimeout(total=5)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            if single_query:
                to_run = [to_run]
            print(str(to_run[0]["kwargs"]["data"]))
            tasks = []
            for task in to_run:
                tasks.append(task["func"](session, *task["args"], **task["kwargs"]))

            return await asyncio.gather(*tasks)


def get_total_amount():
    client = TonCenterTonClient()
    result = client.run_get_method(ORACLE_ADDRESS.to_string(), "TotalAmount", [])
    return result


def tick_in_jetton_transfer(
    watchmaker_address,
    oracle_address,
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

    client = TonCenterTonClient()
    seqno = client.run_get_method(WALLET.address.to_string(), "seqno", [])
    # print("watchmaker_address", watchmaker_address.to_string())
    # print("oracle_address", oracle_address.to_string())
    # print("base_asset_price", base_asset_price)
    # print("quote_asset_transfered", to_bigint(quote_asset_transfered))
    # print("forward_ton_amount", to_bigint(forward_ton_amount))

    body = (
        begin_cell()
        .store_uint(0xF8A7EA5, 32)
        .store_uint(0, 64)
        .store_coins(to_bigint(quote_asset_transfered))
        .store_address(oracle_address)
        .store_address(watchmaker_address)
        .store_bit(False)
        .store_coins(to_bigint(forward_ton_amount))
        .store_ref(forward_info)
        .end_cell()
    )
    # body = JettonWallet().create_transfer_body(
    #     to_address=oracle_address,
    #     jetton_amount=to_bigint(quote_asset_transfered),
    #     forward_amount=to_bigint(forward_ton_amount),
    #     forward_payload=begin_cell().store_ref(forward_info).end_cell().bytes_repr(),
    #     response_address=watchmaker_address,
    #     query_id=0,
    # )
    print(body)
    query = WALLET.create_transfer_message(
        to_addr="kQCQ1B7B7-CrvxjsqgYT90s7weLV-IJB2w08DBslDdrIXucv",
        amount=to_nano(4, "ton"),
        seqno=int(seqno[0][1], 16),
        payload=body,
    )
    boc = query["message"].to_boc(False)

    print("@ SeqNum: ", seqno)
    result = client.send_boc(boc)

    return result


def tick():
    pass


print("@ Total Alarms:", get_total_amount())
tick_in_jetton_transfer(
    watchmaker_address=WALLET.address,
    oracle_address=ORACLE_ADDRESS,
    quote_asset_to_transfer=2,
    base_asset_to_transfer=1,
)
