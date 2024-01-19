import os
from dotenv import load_dotenv

import mysql.connector as connector
import mysql.connector.errors as Error

load_dotenv()


def create_connection():
    try:
        connection = connector.connect(
            host=os.getenv("MYSQL_HOST"),  # Assuming MariaDB is running on localhost
            database=os.getenv("MYSQL_DATABASE"),
            user=os.getenv("MYSQL_USER"),
            password=os.getenv("MYSQL_PASSWORD"),
        )
        if connection.is_connected():
            db_info = connection.get_server_info()
            print("Successfully connected to MariaDB server version ", db_info)
            return connection
    except Error as e:
        print("Error while connecting to MariaDB", e)
        return None


def main():
    connection = create_connection()
    if connection is not None and connection.is_connected():
        # Add your database operations here
        connection.close()


if __name__ == "__main__":
    main()
