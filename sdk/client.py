from decimal import Decimal
import logging
import time
from tonsdk.utils import Address, bytes_to_b64str
from tonsdk.boc import Cell, begin_cell
from tonsdk.contract.wallet import Wallets
from typing import Dict, Tuple, Optional, Literal, Callable, TypedDict
from .arithmetic import FixedFloat
from utils import to_token
from os import getenv
from .ton_center_client import TonCenterClient

OracleMetadata = TypedDict(
    "OracleMetadata",
    {
        "base_asset_address": Address,
        "quote_asset_address": Address,
        "base_asset_decimals": int,
        "quote_asset_decimals": int,
        "min_base_asset_threshold": int,
        "base_asset_wallet_address": Address,
        "quote_asset_wallet_address": Address,
        "is_initialized": bool,
    },
)


class TicTonAsyncClient:
    def __init__(
        self,
        metadata: OracleMetadata,
        toncenter: TonCenterClient,
        mnemonics: Optional[str] = None,
        oracle_addr: Optional[str] = None,
        wallet_version: Literal[
            "v2r1", "v2r2", "v3r1", "v3r2", "v4r1", "v4r2", "hv2"
        ] = "v4r2",
        threshold_price: float = 0.01,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        _, _, _, self.wallet = Wallets.from_mnemonics(mnemonics.split(" "), wallet_version)  # type: ignore
        self.oracle = Address(oracle_addr)
        self.logger = logger

        # TODO: import toncenter client
        self.toncenter = toncenter

        self.threshold_price = threshold_price
        self.metadata = metadata

    @classmethod
    async def init(
        cls: "TicTonAsyncClient",
        mnemonics: Optional[str] = None,
        oracle_addr: Optional[str] = None,
        toncenter_api_key: Optional[str] = None,
        wallet_version: Literal[
            "v2r1", "v2r2", "v3r1", "v3r2", "v4r1", "v4r2", "hv2"
        ] = "v4r2",
        threshold_price: float = 0.01,
        *,
        testnet: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> "TicTonAsyncClient":
        mnemonics = getenv("TICTON_WALLET_MNEMONICS", mnemonics)
        wallet_version = getenv("TICTON_WALLET_VERSION", wallet_version)
        oracle_addr = getenv("TICTON_ORACLE_ADDRESS", oracle_addr)
        toncenter_api_key = getenv("TICTON_TONCENTER_API_KEY", toncenter_api_key)
        threshold_price = getenv("TICTON_THRESHOLD_PRICE", threshold_price)
        assert (
            mnemonics is not None
        ), "mnemonics must be provided, you can either pass it as a parameter or set TICTON_WALLET_MNEMONICS environment variable"
        assert (
            oracle_addr is not None
        ), "oracle_addr must be provided, you can either pass it as a parameter or set TICTON_ORACLE_ADDRESS environment variable"

        logger = logger or logging.getLogger(__name__)

        # TODO: import toncenter client
        toncenter = TonCenterClient(toncenter_api_key, testnet=testnet)
        metadata = await cls._get_oracle_metadata(oracle_addr, toncenter)

        return cls(
            metadata=metadata,
            toncenter=toncenter,
            mnemonics=mnemonics,
            oracle_addr=oracle_addr,
            wallet_version=wallet_version,
            threshold_price=threshold_price,
            logger=logger,
        )

    @staticmethod
    async def _get_oracle_metadata(
        oracle_addr: str, client: TonCenterClient
    ) -> OracleMetadata:
        """
        get the oracle's metadata
        """
        metedata: OracleMetadata = {
            "base_asset_address": Address(
                "0:0000000000000000000000000000000000000000000000000000000000000000"
            ),
            "quote_asset_address": Address(
                "kQBqSpvo4S87mX9tjHaG4zhYZeORhVhMapBJpnMZ64jhrP-A"
            ),
            "base_asset_decimals": 9,
            "quote_asset_decimals": 6,
            "min_base_asset_threshold": 1 * 10**9,
            "base_asset_wallet_address": "",
            "quote_asset_wallet_address": "",
            "is_initialized": True,
        }

        return metedata
        raise NotImplementedError

    async def _convert_price(self, price: float) -> FixedFloat:
        """
        Adjusts the given price by scaling it to match the decimal difference between the quote and base assets in a token pair.
        """
        assert price > 0, "price must be greater than 0"
        assert isinstance(price, float), "price must be a float"
        return (
            FixedFloat(price)
            * 10 ** self.metadata["quote_asset_decimals"]
            / 10 ** self.metadata["base_asset_decimals"]
        )

    async def _get_user_balance(self) -> Tuple[Decimal, Decimal]:
        """
        get the user's balance of baseAsset and quoteAsset in nanoTON

        Returns
        -------
        base_asset_balance : Decimal
            The balance of baseAsset in nanoTON
        quote_asset_balance : Decimal
            The balance of quoteAsset in nanoTON
        """

        async def _get_balance(
            master_address: Address, account_address: Address
        ) -> Decimal:
            if (
                master_address.to_string()
                == "0:0000000000000000000000000000000000000000000000000000000000000000"
            ):
                balance = await self.toncenter.get_address_balance(
                    account_address.to_string()
                )
            else:
                balance = await self.toncenter.get_token_balance(
                    master_address, account_address
                )

            return Decimal(balance)

        base_asset_balance = await _get_balance(
            self.metadata["base_asset_address"], self.wallet.address
        )
        quote_asset_balance = await _get_balance(
            self.metadata["quote_asset_address"], self.wallet.address
        )
        return (base_asset_balance, quote_asset_balance)

    async def _send(
        self,
        to_address: str,
        amount: int,
        seqno: int,
        body: Cell,
        *,
        dry_run: bool = False,
    ):
        """
        _send will send the given amount of tokens to to_address, if dry_run is set to True, it will
        call toncenter simulation api, otherwise it will send the transaction to the network directly.

        Parameters
        ----------
        amount : int
            The amount of TON to be sent
        seqno : int
            The seqno of user's wallet
        body : Cell
            The body of the transaction
        dry_run : bool
            Whether to call toncenter simulation api or not
        """
        print("to_address", to_address)
        if dry_run:
            result = []
        else:
            query = self.wallet.create_transfer_message(
                to_addr=to_address,
                amount=amount,
                seqno=seqno,
                payload=body,
            )
            print("body", bytes_to_b64str(query["message"].to_boc(False)))
            boc = query["message"].to_boc(False)
            result = await self.toncenter.send_boc(boc)

        return result

    async def _estimate_from_oracle_get_method(
        self, alarm_address: str, buy_num: int, new_price: float
    ):
        alarm_info = await self.toncenter.get_alarm_info(alarm_address)

        new_price_ff = await self._convert_price(new_price)
        old_price_ff = FixedFloat(alarm_info["base_asset_price"], skip_scale=True)

        if new_price_ff > old_price_ff:
            # self.wallet will pay quote asset and buy base asset
            need_quote_asset = (
                new_price_ff * 2 * self.metadata["min_base_asset_threshold"]
                + old_price_ff * self.metadata["min_base_asset_threshold"]
            ).to_float()
            need_base_asset = FixedFloat(
                self.metadata["min_base_asset_threshold"]
            ).to_float()
            max_buy_num = alarm_info["base_asset_scale"]
        else:
            # self.wallet will pay base asset and buy quote asset
            need_quote_asset = (
                new_price_ff * 2 * self.metadata["min_base_asset_threshold"]
                - old_price_ff * self.metadata["min_base_asset_threshold"]
            ).to_float()
            need_base_asset = FixedFloat(
                self.metadata["min_base_asset_threshold"]
            ).to_float()
            max_buy_num = alarm_info["quote_asset_scale"]
        can_buy = True
        if buy_num > max_buy_num:
            can_buy = False

        return (can_buy, need_base_asset + 1 * 10**9, need_quote_asset)

    async def _estimate_wind(self, alarm_id: int, buy_num: int, new_price: float):
        alarm_address = await self.toncenter.get_alarm_address(
            self.oracle.to_string(), alarm_id
        )
        alarm_state = await self.toncenter.get_address_state(alarm_address)
        assert alarm_state == "active", "alarm is not active"

        alarm_info = await self.toncenter.get_alarm_info(alarm_address)
        print("alarm_info", alarm_info)

        new_price_ff = await self._convert_price(new_price)
        old_price_ff = FixedFloat(alarm_info["base_asset_price"], skip_scale=True)
        price_delta = abs(new_price_ff - old_price_ff)

        if price_delta < self.threshold_price:
            return None

        (
            can_buy,
            need_base_asset,
            need_quote_asset,
        ) = await self._estimate_from_oracle_get_method(
            alarm_address, buy_num, new_price
        )
        assert can_buy, "buy_num is too large"

        return (need_base_asset, need_quote_asset)

    async def _can_afford(self, need_base_asset: Decimal, need_quote_asset: Decimal):
        base_asset_balance, quote_asset_balance = await self._get_user_balance()
        gas_fee = 1 * 10**9
        if (
            need_base_asset + gas_fee > base_asset_balance
            or need_quote_asset > quote_asset_balance
        ):
            return False
        return True

    async def tick(
        self, price: float, *, timeout: int = 1000, extra_ton: float = 2, **kwargs
    ):
        """
        tick will open a position with the given price and timeout, the total amount
        of baseAsset and quoteAsset will be calculated automatically.

        Parameters
        ----------
        price : float
            The price of the position quoteAsset/baseAsset
        timeout : int
            The timeout of the position in seconds
        extra_ton : float
            The extra ton to be sent to the oracle
        dry_run : bool
            Whether to call toncenter simulation api or not

        Examples
        --------
        Assume the token pair is TON/USDT, the price is 2.5 USDT per TON

        >>> client = TicTonAsyncClient(...)
        >>> await client.init()
        >>> await client.tick(2.5)
        """
        expire_at = int(time.time()) + timeout
        base_asset_price = await self._convert_price(price)
        quote_asset_transfered = FixedFloat(
            to_token(price, self.metadata["quote_asset_decimals"])
        )
        forward_ton_amount = quote_asset_transfered / base_asset_price + to_token(
            extra_ton, self.metadata["base_asset_decimals"]
        )
        base_asset_price = int(base_asset_price.raw_value)
        print(f"base_asset_price: {base_asset_price}")
        quote_asset_transfered = quote_asset_transfered.to_float()
        forward_ton_amount = int(round(forward_ton_amount.to_float(), 0))
        gas_fee = 1 * 10**9

        forward_info = (
            begin_cell()
            .store_uint(0, 8)
            .store_uint(expire_at, 256)
            .store_uint(base_asset_price, 256)
            .end_cell()
        )

        seqno = await self.toncenter.run_get_method(
            self.wallet.address.to_string(), "seqno", []
        )

        body = (
            begin_cell()
            .store_uint(0xF8A7EA5, 32)
            .store_uint(0, 64)
            .store_coins(quote_asset_transfered)
            .store_address(self.oracle)
            .store_address(self.wallet.address)
            .store_bit(False)
            .store_coins(forward_ton_amount)
            .store_ref(forward_info)
            .end_cell()
        )

        jetton_wallet_address = await self.toncenter.get_jetton_wallet(
            self.metadata["quote_asset_address"], self.wallet.address
        )
        result = await self._send(
            to_address=jetton_wallet_address,
            amount=forward_ton_amount + gas_fee,
            seqno=int(seqno, 16),
            body=body,
        )
        return result

    async def ring(self, alarm_id: int, **kwargs):
        """
        ring will close the position with the given alarm_id

        Parameters
        ----------
        alarm_id : int
            The alarm_id of the position to be closed
        dry_run : bool
            Whether to call toncenter simulation api or not

        Examples
        --------
        >>> client = TicTonAsyncClient(...)
        >>> await client.init()
        >>> await client.ring(123)
        """
        seqno = await self.toncenter.run_get_method(
            self.wallet.address.to_string(), "seqno", []
        )
        body = (
            begin_cell()
            .store_uint(0xC3510A29, 32)
            .store_uint(alarm_id, 257)
            .store_uint(alarm_id, 257)
            .end_cell()
        )
        result = await self._send(
            to_address=self.oracle.to_string(),
            amount=1 * 10**9,
            seqno=int(seqno, 16),
            body=body,
        )

        return result

    async def wind(self, alarm_id: int, buy_num: int, new_price: float, **kwargs):
        """
        wind will arbitrage the position with the given alarm_id, buy_num and new_price

        Parameters
        ----------
        alarm_id : int
            The alarm_id of the position to be arbitrage
        buy_num : int
            The number of tokens to be bought, at least 1.
        new_price : float
            The new price of the position quoteAsset/baseAsset
        dry_run : bool
            Whether to call toncenter simulation api or not

        Examples
        --------
        Assume the token pair is TON/USDT, the price is 2.5 USDT per TON. The position is opened with 1 TON and 2.5 USDT with index 123.
        The new price is 5 USDT per TON, the buy_num is 1.

        >>> client = TicTonAsyncClient(...)
        >>> await client.wind(123, 1, 5)
        """
        new_price_ff = await self._convert_price(new_price)
        need_asset_tup = await self._estimate_wind(alarm_id, buy_num, new_price)
        assert (
            need_asset_tup is not None
        ), "The price difference is smaller than threshold price"

        need_base_asset, need_quote_asset = need_asset_tup

        can_afford = await self._can_afford(need_base_asset, need_quote_asset)

        assert can_afford, "not enough balance"

        seqno = await self.toncenter.run_get_method(
            self.wallet.address.to_string(), "seqno", []
        )
        forward_info = (
            begin_cell()
            .store_uint(1, 8)
            .store_uint(alarm_id, 256)
            .store_uint(buy_num, 32)
            .store_uint(int(new_price_ff.raw_value), 256)
            .end_cell()
        )
        need_base_asset = int(need_base_asset)
        need_quote_asset = int(need_quote_asset)
        print(f"new_price: {int(new_price_ff.raw_value)}")
        print(need_base_asset, need_quote_asset)

        body = (
            begin_cell()
            .store_uint(0xF8A7EA5, 32)
            .store_uint(0, 64)
            .store_coins(need_quote_asset)
            .store_address(self.oracle)
            .store_address(self.wallet.address)
            .store_bit(False)
            .store_coins(need_base_asset)
            .store_ref(forward_info)
            .end_cell()
        )

        jetton_wallet_address = await self.toncenter.get_jetton_wallet(
            self.metadata["quote_asset_address"], self.wallet.address
        )

        result = await self._send(
            to_address=jetton_wallet_address,
            amount=int(need_base_asset) + 1 * 10**9,
            seqno=int(seqno, 16),
            body=body,
        )

        return result

    async def subscribe(
        self,
        on_tick_success: Optional[Callable] = None,
        on_ring_success: Optional[Callable] = None,
        on_wind_success: Optional[Callable] = None,
    ):
        """
        subscribe will subscribe the oracle's transactions, handle the transactions and call the
        given callbacks.
        """
        raise NotImplementedError
