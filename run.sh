#!/bin/sh
python ./market_price.py &
python ./bot.py &
wait
