from decimal import Decimal, getcontext

# Set the precision for Decimal operations
getcontext().prec = 128


def float_conversion(value, precision=64):
    return Decimal(value) * (Decimal(2) ** precision)


def int_conversion(value):
    return Decimal(value) / (Decimal(2) ** 64)


def to_token(value, decimals):
    return Decimal(value) * (Decimal(10) ** decimals)
