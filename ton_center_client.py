from tonsdk.provider import ToncenterClient, prepare_address, address_state

import aiohttp


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

        return result[0][1]

    async def get_address_information(self, address):
        address = prepare_address(address)
        result = await self._run(self.provider.raw_get_account_state(address))

        result["state"] = address_state(result)

        return result["state"]

    async def send_boc(self, boc):
        return await self._run(self.provider.raw_send_message(boc))

    async def _run(self, to_run):
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            func = to_run["func"]
            args = to_run["args"]
            kwargs = to_run["kwargs"]
            return await func(session, *args, **kwargs)
