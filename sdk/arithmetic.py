from typing import Union
from decimal import Decimal


class FixedFloat:
    def __init__(
        self,
        value: Union[int, float, str, Decimal, "FixedFloat"],
        *,
        precision: int = 64,
        base: int = 2,
        skip_scale: bool = False,
    ):
        assert isinstance(
            value, (int, float, str, Decimal, FixedFloat)
        ), "Invalid type for FixedFloat, must be int, float, str, or Decimal"
        if isinstance(value, FixedFloat):
            assert value.precision == precision, "Precision must match for FixedFloat"
            assert value.base == base, "Base must match for FixedFloat"
            self.raw_value = value.raw_value
            return

        self.base = base
        self.precision = precision
        self.factor = Decimal(base) ** precision
        if skip_scale:
            self.raw_value = Decimal(value)
        else:
            self.raw_value = self._cast(value)

    def _cast(self, value: Union[int, float, str, Decimal]) -> Decimal:
        return Decimal(value) * self.factor

    def to_float(self) -> Decimal:
        """
        Convert fixed point number to float in human readable format
        """
        return Decimal(self.raw_value) / self.factor

    def to_int(self) -> int:
        """
        Convert fixed point number to bigint in human readable format
        """
        return int(Decimal(self.raw_value).to_integral_value() // self.factor)

    def __repr__(self):
        return f"FixedFloat(raw_value={self.raw_value}, human_format={self.to_float()})"

    def __str__(self):
        return self.__repr__()

    def __add__(self, other):
        if isinstance(other, FixedFloat):
            return FixedFloat(
                self.raw_value + other.raw_value,
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        elif isinstance(other, (int, float, str, Decimal)):
            return FixedFloat(
                self.raw_value + self._cast(other),
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        raise TypeError(f"Cannot add FixedFloat and {type(other)}")

    def __sub__(self, other):
        if isinstance(other, FixedFloat):
            return FixedFloat(
                self.raw_value - other.raw_value,
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        elif isinstance(other, (int, float, str, Decimal)):
            return FixedFloat(
                self.raw_value - self._cast(other),
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        raise TypeError(f"Cannot subtract FixedFloat and {type(other)}")

    def __mul__(self, other):
        if isinstance(other, FixedFloat):
            return FixedFloat(
                self.raw_value * other.raw_value / self.factor,
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        elif isinstance(other, (int, float, str, Decimal)):
            return FixedFloat(
                self.raw_value * Decimal(other),
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        raise TypeError(f"Cannot multiply FixedFloat and {type(other)}")

    def __rmul__(self, other):
        return self.__mul__(other)

    def __truediv__(self, other):
        if isinstance(other, FixedFloat):
            return FixedFloat(
                self.raw_value / other.raw_value,
                precision=self.precision,
                base=self.base,
            )
        elif isinstance(other, (int, float, str, Decimal)):
            return FixedFloat(
                self.raw_value / Decimal(other),
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        raise TypeError(f"Cannot divide FixedFloat and {type(other)}")

    def __floordiv__(self, other):
        if isinstance(other, FixedFloat):
            return FixedFloat(
                self.raw_value // other.raw_value,
                precision=self.precision,
                base=self.base,
            )
        elif isinstance(other, (int, float, str, Decimal)):
            return FixedFloat(
                self.raw_value // Decimal(other),
                precision=self.precision,
                base=self.base,
                skip_scale=True,
            )
        raise TypeError(f"Cannot divide FixedFloat and {type(other)}")

    def __abs__(self) -> "FixedFloat":
        return FixedFloat(abs(self.raw_value), precision=self.precision, base=self.base)

    def __eq__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value == other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value == self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __ne__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value != other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value != self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __lt__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value < other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value < self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __gt__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value > other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value > self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __le__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value <= other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value <= self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __ge__(self, other) -> bool:
        if isinstance(other, FixedFloat):
            return self.raw_value >= other.raw_value
        elif isinstance(other, (int, float, str, Decimal)):
            return self.raw_value >= self._cast(other)
        raise TypeError(f"Cannot compare FixedFloat and {type(other)}")

    def __bool__(self) -> bool:
        return bool(self.raw_value)


def to_token(value: Union[int, float, str, Decimal], decimals: int) -> Decimal:
    return Decimal(value) * (Decimal(10) ** decimals)


def token_to_float(value: Union[int, float, str, Decimal], decimals: int) -> Decimal:
    return float(Decimal(value) / (Decimal(10) ** decimals))
