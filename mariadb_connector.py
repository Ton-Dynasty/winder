import os
import re
from dotenv import load_dotenv
import asyncio
from typing import Literal, Optional

import mysql.connector as connector

import logging

# set up logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


load_dotenv()


class Alarm:
    def __init__(
        self,
        id: int,
        price: Optional[int] = 0,
        address: Optional[str] = None,
        state: Literal["uninitialized", "active"] = "active",
        is_mine: bool = False,
    ):
        self.id = id
        self.address = address
        self.state = state
        self.price = price
        self.is_mine = is_mine


async def create_connection():
    try:
        connection = connector.connect(
            host=os.getenv("MYSQL_HOST"),  # Assuming MariaDB is running on localhost
            database=os.getenv("MYSQL_DATABASE"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
        )
        if connection.is_connected():
            return connection
        else:
            return None
    except Exception as e:
        logger.error(f"Error while connecting to MariaDB {e}")


async def init():
    try:
        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS alarms (
                id INT PRIMARY KEY,
                address VARCHAR(255),
                state VARCHAR(100) DEFAULT 'active'
                price DECIMAL(16, 9) DEFAULT 0
                is_mine BOOLEAN DEFAULT FALSE
            )
            """
            cursor.execute(create_table_sql)
            connection.commit()
            connection.close()
            logger.info("Successfully Initialized MariaDB")

            return True

    except Exception as e:
        logger.error("Error while initializing MariaDB", e)
        return False


async def get_alarm_from_db(filter: Optional[str] = None):
    try:
        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            select_sql = """
            SELECT id, address, state, price, is_mine FROM alarms
            WHERE {}
            """
            select_sql = select_sql.format("1=1" if filter is None else filter)
            cursor.execute(select_sql)
            result = []
            for id, address, state, price, is_mine in cursor.fetchall():
                alarm = Alarm(id, price, address, state, is_mine)
                result.append(alarm)

            cursor.close()
            connection.close()
            return result

    except Exception as e:
        logger.error(f"Error while fetching alarm info from MariaDB {e}")
        return None


async def update_alarm_to_db(alarms: list[Alarm]):
    try:
        if alarms is None or len(alarms) == 0:
            return False

        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            update_sql = """
                INSERT INTO alarms (id, address, state, price, is_mine)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                address = VALUES(address),
                state = VALUES(state),
                price = VALUES(price),
                is_mine = VALUES(is_mine)
            """
            insert_list = []
            for alarm in alarms:
                insert_list.append(
                    (
                        alarm.id,
                        alarm.address,
                        alarm.state,
                        alarm.price,
                        alarm.is_mine,
                    )
                )
            cursor.executemany(update_sql, insert_list)
            connection.commit()
            cursor.close()
            connection.close()

            return True

        return False

    except Exception as e:
        logger.error(f"Error while updating alarm info to MariaDB {e}")


async def main():
    flag = False
    while not flag:
        flag = await init()


if __name__ == "__main__":
    asyncio.run(main())
