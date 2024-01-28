from decimal import Decimal
import logging
import time
from tonsdk.utils import Address
from tonsdk.boc import Cell
from tonsdk.contract.wallet import Wallets
from typing import Dict, Tuple, Optional, Literal, Callable, TypedDict
from arithmetic import FixedFloat
from utils import to_token
from os import getenv

OracleMetadata = TypedDict(
    "OracleMetadata",
    {
        "base_asset_address": str,
        "quote_asset_address": str,
        "base_asset_decimals": int,
        "quote_asset_decimals": int,
        "min_base_asset_threshold": int,
        "base_asset_wallet_address": str,
        "quote_asset_wallet_address": str,
    },
)


class TicTonAsyncClient:
    async def __init__(
        self,
        mnemonics: Optional[str] = None,
        oracle_addr: Optional[str] = None,
        toncenter_api_key: Optional[str] = None,
        wallet_version: Optional[
            Literal["v2r1", "v2r2", "v3r1", "v3r2", "v4r1", "v4r2", "hv2"]
        ] = None,
        *,
        logger: Optional[logging.Logger] = None
    ) -> None:
        mnemonics = getenv("TICTON_WALLET_MNEMONICS", mnemonics)
        wallet_version = getenv("TICTON_WALLET_VERSION", wallet_version or "v4r2")
        oracle_addr = getenv("TICTON_ORACLE_ADDRESS", oracle_addr)

        assert (
            mnemonics is not None
        ), "mnemonics must be provided, you can either pass it as a parameter or set TICTON_WALLET_MNEMONICS environment variable"
        assert (
            oracle_addr is not None
        ), "oracle_addr must be provided, you can either pass it as a parameter or set TICTON_ORACLE_ADDRESS environment variable"

        _, _, _, self.wallet = Wallets.from_mnemonics(mnemonics.split(" "), wallet_version)  # type: ignore
        self.oracle = Address(oracle_addr)
        self.logger = logger or logging.getLogger(__name__)

        # TODO: import toncenter client
        self.toncenter = None

        self.metadata = await self._get_oracle_metadata()

    async def _get_oracle_metadata(self) -> OracleMetadata:
        """
        get the oracle's metadata
        """
        raise NotImplementedError

    async def _convert_price(self, price: float) -> FixedFloat:
        """
        Adjusts the given price by scaling it to match the decimal difference between the quote and base assets in a token pair.
        """
        assert price > 0, "price must be greater than 0"
        assert isinstance(price, float), "price must be a float"
        return FixedFloat(price) * 10 ** (
            self.metadata["quote_asset_decimals"] - self.metadata["base_asset_decimals"]
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
        raise NotImplementedError

    async def _send(
        self, amount: int, seqno: int, body: Cell, *, dry_run: bool = False
    ):
        """
        _send will send the given amount of tokens to the oracle, if dry_run is set to True, it will
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
        raise NotImplementedError

    async def tick(
        self, price: float, *, timeout: int = 30, extra_ton: float = 1, **kwargs
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
        >>> await client.tick(2.5)
        """
        price = await self._convert_price(price)
        expire_at = int(time.time()) + timeout
        raise NotImplementedError

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
        >>> await client.ring(123)
        """
        raise NotImplementedError

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
        assert buy_num >= 1, "buy_num must be greater than or equal to 1"
        new_price = await self._convert_price(new_price)
        raise NotImplementedError

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
