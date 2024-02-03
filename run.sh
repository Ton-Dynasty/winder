#!/bin/sh

# init database
python ./mariadb_connector.py

# run market price and bot
python ./market_price.py &
python ./subscriber.py &
python ./bot.py &
wait
