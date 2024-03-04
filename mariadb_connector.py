import os
import re
from dotenv import load_dotenv
import asyncio
from typing import Literal, Optional, Union

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
        price: Optional[float] = 0,
        created_at: Optional[int] = 0,
        state: Literal["uninitialized", "active"] = "active",
        is_mine: bool = False,
        remain_scale: int = 1,
    ):
        self.id = id
        self.state = state
        self.price = price
        self.is_mine = is_mine
        self.remain_scale = remain_scale
        self.created_at = created_at

    def __repr__(self):
        return f"Alarm(id={self.id}, state={self.state}, price={self.price}, is_mine={self.is_mine}), remain_scale={self.remain_scale}, created_at={self.created_at}\n"


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
                state VARCHAR(100) DEFAULT 'active',
                price DECIMAL(16, 9) DEFAULT 0,
                is_mine BOOLEAN DEFAULT FALSE,
                remain_scale INT DEFAULT 1,
                created_at INT DEFAULT 0
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
            SELECT id,state, price, is_mine, remain_scale, created_at FROM alarms
            WHERE {}
            """
            select_sql = select_sql.format("1=1" if filter is None else filter)
            cursor.execute(select_sql)
            result = []
            for (
                id,
                state,
                price,
                is_mine,
                remain_scale,
                created_at,
            ) in cursor.fetchall():
                alarm = Alarm(
                    id=id,
                    state=state,
                    price=price,
                    is_mine=is_mine,
                    remain_scale=remain_scale,
                    created_at=created_at,
                )
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
                INSERT INTO alarms (id, state, price, is_mine, remain_scale, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                state = VALUES(state),
                remain_scale = VALUES(remain_scale)
            """
            insert_list = []
            for alarm in alarms:
                insert_list.append(
                    (
                        alarm.id,
                        alarm.state,
                        alarm.price,
                        alarm.is_mine,
                        alarm.remain_scale,
                        alarm.created_at,
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


async def get_latest_alarm_id():
    try:
        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            select_sql = """
            SELECT id FROM alarms ORDER BY id DESC LIMIT 1
            """
            cursor.execute(select_sql)
            latest_id = cursor.fetchone()

            cursor.close()
            connection.close()

            return latest_id[0] if latest_id is not None else 0
        else:
            return 0

    except Exception as e:
        logger.error(f"Error while fetching latest alarm id from MariaDB {e}")
        return 0


async def main():
    flag = False
    while not flag:
        flag = await init()


if __name__ == "__main__":
    asyncio.run(main())
