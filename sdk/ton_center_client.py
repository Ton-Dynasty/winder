from tonsdk.provider import ToncenterClient, prepare_address, address_state

import aiohttp
import json
from typing import Dict


class ToncenterWrongResult(Exception):
    def __init__(self, code):
        self.code = code


class TonCenterClient:
    def __init__(self, api_key, testnet=True):
        if testnet:
            self.provider = ToncenterClient(
                base_url="https://testnet.toncenter.com/api/v2/",
                api_key=api_key,
            )
        else:
            self.provider = ToncenterClient(
                base_url="https://toncenter.com/api/v2/",
                api_key=api_key,
            )

    async def run_get_method(self, addr: str, method: str, stack: list):
        addr = prepare_address(addr)
        result = await self._run(self.provider.raw_run_method(addr, method, stack))

        if result.get("@type") == "smc.runResult" and "stack" in result:
            result = result["stack"]

        return result[0][1]

    async def get_address_state(self, address):
        req = {
            "func": self.__jsonrpc_request,
            "args": ["getAddressState"],
            "kwargs": {"params": {"address": address}},
        }
        result = await self._run(req)

        return result

    async def get_address_balance(self, address):
        req = {
            "func": self.__jsonrpc_request,
            "args": ["getAddressBalance"],
            "kwargs": {"params": {"address": address}},
        }
        result = await self._run(req)

        return result

    ## Todo
    async def get_token_balance(self, master_address, account_address):
        # get jetton wallet address from master address
        jetton_wallet_address = await self.run_get_method(
            addr=master_address,
            method="get_wallet_address",
            stack=[[slice, account_address]],
        )
        print(f"jetton_wallet_address: {jetton_wallet_address}")
        # get token balance from jetton wallet address
        # req = {
        #     "func": self.__jsonrpc_request,
        #     "args": ["getTokenData"],
        #     "kwargs": {"params": {"address": address}},
        # }
        # result = await self._run(req)
        # return result

    async def get_address_information(self, address):
        address = prepare_address(address)
        result = await self._run(self.provider.raw_get_account_state(address))

        result["state"] = address_state(result)

        return result["state"]

    async def send_boc(self, boc):
        return await self._run(self.provider.raw_send_message(boc))

    async def _run(self, to_run):
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            func = to_run["func"]
            args = to_run["args"]
            kwargs = to_run["kwargs"]
            return await func(session, *args, **kwargs)

    async def __post_request(self, session, url, data):
        async with session.post(
            url, data=json.dumps(data), headers=self.__headers()
        ) as resp:
            return await self.__parse_response(resp)

    async def __jsonrpc_request(
        self, session, method: str, params: Dict, id: str = "1", jsonrpc: str = "2.0"
    ):
        payload = {
            "id": id,
            "jsonrpc": jsonrpc,
            "method": method,
            "params": params,
        }

        async with session.post(
            self.provider.base_url + "jsonRPC", json=payload, headers=self.__headers()
        ) as resp:
            return await self.__parse_response(resp)

    def __headers(self):
        headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
        }
        if self.provider.api_key:
            headers["X-API-Key"] = self.provider.api_key

        return headers

    async def __parse_response(self, resp):
        try:
            resp = await resp.json()
        except Exception:  # TODO: catch correct exceptions
            raise ToncenterWrongResult(resp.status)

        if not resp["ok"]:
            raise ToncenterWrongResult(resp["code"])

        return resp["result"]
