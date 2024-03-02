from typing import List, Union
from decimal import Decimal


class ProfitableAlarm:
    def __init__(
        self,
        id: int,
        price_delta: float,
        need_base_asset: Union[int, Decimal],
        need_quote_asset: Union[int, Decimal],
        buy_num: int,
    ):
        self.id = id
        self.price_delta = price_delta
        self.need_base_asset = Decimal(need_base_asset)
        self.need_quote_asset = Decimal(need_quote_asset)
        self.buy_num = buy_num
        self.except_profit = price_delta * buy_num

    def __repr__(self):
        return f"ProfitableAlarm({self.id}, {self.price_delta}, {int(self.need_base_asset)}, {int(self.need_quote_asset)}, {self.buy_num}, {self.except_profit})\n"


class Balance:
    def __init__(
        self, base_asset: Union[int, Decimal], quote_asset: Union[int, Decimal]
    ):
        self.base_asset = base_asset
        self.quote_asset = quote_asset

    async def update_balance(
        self,
        need_base_asset: Union[int, Decimal],
        need_quote_asset: Union[int, Decimal],
    ):
        if need_base_asset > self.base_asset:
            self.base_asset = 0
        else:
            self.base_asset -= need_base_asset

        if need_quote_asset > self.quote_asset:
            self.quote_asset = 0
        else:
            self.quote_asset -= need_quote_asset

    def __repr__(self):
        return f"Balance({int(self.base_asset)}, {int(self.quote_asset)})"


async def greedy_strategy(alarms: List[ProfitableAlarm], balance: Balance):
    alarms = sorted(alarms, key=lambda x: x.except_profit, reverse=True)
    for alarm in alarms:
        if (
            balance.base_asset >= alarm.need_base_asset
            and balance.quote_asset >= alarm.need_quote_asset
        ):
            await balance.update_balance(alarm.need_base_asset, alarm.need_quote_asset)

            yield alarm
        else:
            return
    return
