from decimal import Decimal
import logging
import time
from tonsdk.utils import Address, bytes_to_b64str
from tonsdk.boc import Cell, begin_cell
from tonsdk.contract.wallet import Wallets
from tonpy import CellSlice
from typing import Dict, Tuple, Optional, Literal, Callable, TypedDict, List
from .arithmetic import FixedFloat, to_token, token_to_float
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
        threshold_price: float = 0.7,
        *,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        _, _, _, self.wallet = Wallets.from_mnemonics(mnemonics.split(" "), wallet_version)  # type: ignore
        self.oracle = Address(oracle_addr)
        if logger is None:
            self.logger = logging.getLogger(__name__)
            self.logger.setLevel(logging.INFO)
            console_handler = logging.StreamHandler()
            self.logger.addHandler(console_handler)
        else:
            self.logger = logger

        # TODO: import toncenter client
        self.toncenter = toncenter

        self.threshold_price = threshold_price
        self.metadata = metadata

        self.logger.info("TicTonAsyncClient initialized")

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
        metadata_res = await client.get_oracle_data(oracle_addr, "getOracleData", [])
        assert len(metadata_res) == 8, "invalid oracle data"

        base_asset_address = CellSlice(metadata_res[0][1]["bytes"]).load_address()
        quote_asset_address = CellSlice(metadata_res[1][1]["bytes"]).load_address()
        base_asset_decimals = int(metadata_res[2][1], 16)
        quote_asset_decimals = int(metadata_res[3][1], 16)
        min_base_asset_threshold = int(metadata_res[4][1], 16)
        base_asset_wallet_address = CellSlice(
            metadata_res[5][1]["bytes"]
        ).load_address()
        quote_asset_wallet_address = CellSlice(
            metadata_res[6][1]["bytes"]
        ).load_address()
        is_initialized = bool(metadata_res[7][1])

        metadata: OracleMetadata = {
            "base_asset_address": Address(base_asset_address),
            "quote_asset_address": Address(quote_asset_address),
            "base_asset_decimals": base_asset_decimals,
            "quote_asset_decimals": quote_asset_decimals,
            "min_base_asset_threshold": min_base_asset_threshold,
            "base_asset_wallet_address": Address(base_asset_wallet_address),
            "quote_asset_wallet_address": Address(quote_asset_wallet_address),
            "is_initialized": is_initialized,
        }

        return metadata

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
                master_address.to_string(False)
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
        query = self.wallet.create_transfer_message(
            to_addr=to_address,
            amount=amount,
            seqno=seqno,
            payload=body,
        )
        boc = query["message"].to_boc(False)
        result = await self.toncenter.send_boc(boc)

        return result

    async def _estimate_from_oracle_get_method(
        self, alarm_address: str, buy_num: int, new_price: int
    ):
        result = await self.toncenter.get_estimate(
            alarm_address,
            "getEstimate",
            [
                ["num", buy_num],
                [
                    "num",
                    new_price,
                ],
            ],
        )
        print(result)
        can_buy = bool(int(result[0][1], 16))
        need_base_asset = int(result[1][1], 16) + 0.2 * 10**9  # add gas fee
        need_quote_asset = int(result[2][1], 16)
        print(can_buy, need_base_asset, need_quote_asset)

        return (can_buy, need_base_asset, need_quote_asset)

    async def _estimate_wind(self, alarm_id: int, buy_num: int, new_price: float):
        alarm_address = await self.toncenter.get_alarm_address(
            self.oracle.to_string(), alarm_id
        )
        alarm_state = await self.toncenter.get_address_state(alarm_address)
        assert alarm_state == "active", "alarm is not active"

        alarm_info = await self.toncenter.get_alarm_info(alarm_address)

        new_price_ff = await self._convert_price(new_price)
        old_price_ff = FixedFloat(alarm_info["base_asset_price"], skip_scale=True)
        price_delta = abs(new_price_ff - old_price_ff)

        if price_delta < self.threshold_price:
            return None, alarm_info

        (
            can_buy,
            need_base_asset,
            need_quote_asset,
        ) = await self._estimate_from_oracle_get_method(
            alarm_address, buy_num, int(new_price_ff.raw_value)
        )
        assert can_buy, "buy_num is too large"

        return (Decimal(need_base_asset), Decimal(need_quote_asset)), alarm_info

    async def _can_afford(self, need_base_asset: Decimal, need_quote_asset: Decimal):
        base_asset_balance, quote_asset_balance = await self._get_user_balance()
        gas_fee = 1 * 10**9
        if (
            need_base_asset + gas_fee > base_asset_balance
            or need_quote_asset > quote_asset_balance
        ):
            return False
        return True

    async def _parse(self, in_msg_body: str, out_msg_body: List[str]):
        """
        parse the in_msg_body and out_msg_body
        """
        # TODO
        return None

    async def tick(
        self, price: float, *, timeout: int = 1000, extra_ton: float = 0.1, **kwargs
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
        assert extra_ton >= 0.1, "extra_ton must be greater than or equal to 0.1"
        assert price > 0, "price must be greater than 0"
        expire_at = int(time.time()) + timeout
        base_asset_price = await self._convert_price(price)
        quote_asset_transfered = FixedFloat(
            to_token(price, self.metadata["quote_asset_decimals"])
        )
        forward_ton_amount = quote_asset_transfered / base_asset_price + to_token(
            extra_ton, self.metadata["base_asset_decimals"]
        )
        base_asset_price = int(base_asset_price.raw_value)
        quote_asset_transfered = quote_asset_transfered.to_float()
        forward_ton_amount = int(round(forward_ton_amount.to_float(), 0))
        gas_fee = int(0.13 * 10**9)

        can_afford = await self._can_afford(
            Decimal(forward_ton_amount + gas_fee), quote_asset_transfered
        )
        assert can_afford, "not enough balance"

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

        args = [
            price,
            token_to_float(
                forward_ton_amount + gas_fee, self.metadata["base_asset_decimals"]
            ),
            token_to_float(
                quote_asset_transfered, self.metadata["quote_asset_decimals"]
            ),
        ]
        log_info = (
            "Tick Success, tick price: {}, spend base asset: {}, spend quote asset: {}"
        ).format(*args)
        self.logger.info(log_info)

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
        >>> client = TicTonAsyncClient.init(...)
        >>> await client.ring(123)
        """
        alarm_address = await self.toncenter.get_alarm_address(
            self.oracle.to_string(), alarm_id
        )
        alarm_state = await self.toncenter.get_address_state(alarm_address)
        assert alarm_state == "active", "alarm is not exist"

        seqno = await self.toncenter.run_get_method(
            self.wallet.address.to_string(), "seqno", []
        )
        gas_fee = int(0.35 * 10**9)
        body = (
            begin_cell()
            .store_uint(0xC3510A29, 32)
            .store_uint(alarm_id, 257)
            .store_uint(alarm_id, 257)
            .end_cell()
        )
        result = await self._send(
            to_address=self.oracle.to_string(),
            amount=gas_fee,
            seqno=int(seqno, 16),
            body=body,
        )

        args = [alarm_id]
        log_info = "Ring Success, alarm id: {}".format(*args)
        self.logger.info(log_info)

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

        >>> client = TicTonAsyncClient.init(...)
        >>> await client.wind(123, 1, 5)
        """
        assert new_price > 0, "new_price must be greater than 0"
        assert isinstance(buy_num, int), "buy_num must be an int"
        assert buy_num > 0, "buy_num must be greater than 0"

        new_price_ff = await self._convert_price(new_price)
        need_asset_tup, alarm_info = await self._estimate_wind(
            alarm_id, buy_num, new_price
        )
        print(alarm_info)
        assert (
            need_asset_tup is not None
        ), "The price difference is smaller than threshold price"

        need_base_asset, need_quote_asset = need_asset_tup

        seqno = await self.toncenter.run_get_method(
            self.wallet.address.to_string(), "seqno", []
        )

        gas_fee = int(0.13 * 10**9)

        can_afford = await self._can_afford(
            Decimal(need_base_asset + gas_fee), need_quote_asset
        )
        assert can_afford, "not enough balance"

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
            amount=int(need_base_asset) + gas_fee,
            seqno=int(seqno, 16),
            body=body,
        )

        args = [
            alarm_id,
            buy_num,
            new_price,
            token_to_float(need_base_asset, self.metadata["base_asset_decimals"]),
            token_to_float(need_quote_asset, self.metadata["quote_asset_decimals"]),
        ]
        log_info = (
            "Wind Success, alarm id: {}, buy num: {}, wind price: {}, spend base asset: {}, spend quote asset: {}"
        ).format(*args)
        self.logger.info(log_info)

        return result

    async def subscribe(
        self,
        to_lt: int = 0,
        on_tick_success: Optional[Callable] = None,
        on_ring_success: Optional[Callable] = None,
        on_wind_success: Optional[Callable] = None,
    ):
        """
        subscribe will subscribe the oracle's transactions, handle the transactions and call the
        given callbacks.
        """
        while True:
            try:
                if to_lt == 0:
                    params = {"address": self.oracle.to_string(), "limit": 1}
                else:
                    params = {
                        "address": self.oracle.to_string(),
                        "to_lt": to_lt,
                    }
                result = await self.toncenter.get_transactions(params)

                for transaction_tree in result:
                    tx_lt = transaction_tree["transaction_id"]["lt"]
                    in_msg_body = transaction_tree["in_msg"]["msg_data"]["body"]
                    out_msg_body = []
                    for out_msg in transaction_tree["out_msgs"]:
                        out_msg_body.append(out_msg["msg_data"]["body"])

                    if to_lt < int(tx_lt):
                        to_lt = int(tx_lt) + 1
                    print(in_msg_body)
                    print(out_msg_body)

            except Exception as e:
                self.logger.error(f"Error while subscribing {e}")
                continue
