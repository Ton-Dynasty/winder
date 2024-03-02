# Ticton Oracle Bot

## Overview
The **Ticton Oracle Bot** is an arbitrage bot that operates by fetching the average market price of TON/USDT from multiple exchanges. It then quotes this price to the Ticton Oracle. In doing so, it seeks arbitrage opportunities among other quoters. 

## Prerequisites
- [Docker](https://docs.docker.com/engine/install/)
- [Docker Compose](https://docs.docker.com/compose/install/)

## Setting Up the Environment
1. **Clone the Repository**: Clone this repository to your local machine.
   ```bash
   git clone https://github.com/Ton-Dynasty/ticton-oracle-automation.git
   ```
2. **Change Directory**:
   ```bash
   cd ticton-oracle-automation
   ```
3. **Environment Variables**:
   - Create a `.env` file in the root directory of the project.
   - Fill out your `.env` file using `.env.example` as a guide.
   - Below are the parameters that need to be modified in `.env` file
     - `TICTON_TONCENTER_API_KEY`: Obtain your Ton Center Testnet API key from [@tonapibot](https://t.me/tonapibot).
     - `TICTON_WALLET_MNEMONICS`: A space-separated list of mnemonics used for wallet authentication and operations.
     - `TICTON_ORACLE_ADDRESS`: The Address of ticton oracle.
     - `TICTON_THRESHOLD_PRICE`: A float value that sets a threshold price, which is the minimum price difference arbitrage bots look for to decide whether to wind the alarm.
     - `MY_ADDRESS`: Your Ton wallet address.

## Running the Application
1. **Docker Compose**: Navigate to the root directory of the project where the `docker-compose.yml` file is located.
2. **Start the Application**:
   - Run the following command:
     ```bash
     docker-compose up -d
     ```
   - This command will start all the services defined in your `docker-compose.yml` file.
   - Ensure that the `.env` file is correctly set up, as the Docker containers will rely on these environment variables.
3. **Check the Logs**:
   - Run the following command to check the logs:
     ```bash
     docker logs ticton-oracle-bot-app-1 -f
     ```
4. **Stop the Application**:
   - Run the following command to stop the application:
     ```bash
     docker stop ticton-oracle-bot-app-1
     ```
6. **Restart the Applicaiton**:
   - Run the following command to restart the application:
     ```bash
     docker restart ticton-oracle-bot-app-1

## Completely Terminate the Application
```bash
docker compose down
docker system prune -a --volumes
rm -rf maria-db
```
     

