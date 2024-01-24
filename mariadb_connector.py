import os
from dotenv import load_dotenv
import asyncio

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
                state VARCHAR(100),
                price DECIMAL(16, 9)
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


async def get_alarm_from_db():
    try:
        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            select_sql = "SELECT * FROM {}"
            select_sql = select_sql.format("alarms")
            cursor.execute(select_sql)
            result = {}
            for id, address, state, price in cursor.fetchall():
                result[id] = {}
                result[id]["address"] = address
                result[id]["state"] = state
                result[id]["price"] = price

            cursor.close()
            connection.close()
            return result

    except Exception as e:
        logger.error(f"Error while fetching alarm info from MariaDB {e}")
        return None


async def update_alarm_to_db(alarm_dict):
    try:
        if alarm_dict is None:
            return None
        connection = await create_connection()
        if connection is not None and connection.is_connected():
            cursor = connection.cursor()
            update_sql = """
            INSERT INTO {} (id, address, state, price)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE address = VALUES(address), state = VALUES(state), price = VALUES(price)
            """
            update_sql = update_sql.format("alarms")
            insert_list = []
            for alarm_id, alarm_info in alarm_dict.items():
                insert_list.append(
                    (
                        alarm_id,
                        alarm_info["address"],
                        alarm_info["state"],
                        alarm_info["price"],
                    )
                )
            cursor.executemany(update_sql, insert_list)
            connection.commit()
            cursor.close()
            connection.close()

    except Exception as e:
        logger.error(f"Error while updating alarm info to MariaDB {e}")


async def main():
    flag = False
    while not flag:
        flag = await init()


if __name__ == "__main__":
    asyncio.run(main())
