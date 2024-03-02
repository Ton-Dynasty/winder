#!/bin/sh

# init database
python ./mariadb_connector.py

python ./bot.py
