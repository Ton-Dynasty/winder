import asyncio
import os
from dotenv import load_dotenv
from sdk import FixedFloat, to_token, TicTonAsyncClient

load_dotenv()


async def init_test():
    client = TicTonAsyncClient(
        mnemonics=os.getenv("MNEMONICS"),
        oracle_addr=os.getenv("ORACLE_ADDRESS"),
        toncenter_api_key=os.getenv("TEST_TONCENTER_API_KEY"),
        testnet=True,
    )
    await client.init()

    print(client.metadata)
    base_bal, quote_bal = await client._get_user_balance()
    print("base_bal", base_bal)
    print("quote_bal", quote_bal)


async def main():
    await init_test()


if __name__ == "__main__":
    asyncio.run(main())
