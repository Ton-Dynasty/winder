# 🚀 Tic Ton Oracle Competition 2: Arbitrage 🚀
[![Static Badge](https://img.shields.io/badge/Tic_Ton-Telegram-blue?style=for-the-badge&logo=Telegram&labelColor=blue)](https://t.me/TictonOfficial)
[![Static Badge](https://img.shields.io/badge/Tic_Ton-Twitter-black?style=for-the-badge&logo=X&labelColor=black)](https://twitter.com/TicTonOracle)

![Tic ToN 128](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/908f33c6-b2f1-4f79-bf8b-ad132c364929)
## How To Join ?

- Join our [Community](https://t.me/TictonOfficial) and register via the [TicTon bot](https://t.me/TicTon_bot) and run the program from [GitHub](https://github.com/Ton-Dynasty/ticton-oracle-automation/tree/main). 

- Contributors to price stability earn points.
- Top 50% participants receive 💎 NFTs. 
- Priority: 💎 > 🥇 > 🥈 > 🥉
- Higher-tier NFTs will get priority for early TIC TOKEN releases.
- Testing Period: March 2nd to March 10th.
> [!IMPORTANT]
> We also have **⭐️ TicTon Oracle Competition1: Tick & Ring ⭐️** for general users, which can refer to the following [Step-by-Step: How to Earn NFTs Playing Tic Ton Tournament](https://www.youtube.com/watch?v=LCuTCQmP_rI) and [Introduction of Competition1](https://t.me/TictonOfficial/52).

## Overview
The **Ticton Oracle Bot** is an arbitrage bot that checks the current Alarm quotes on the Oracle by fetching the average market price of TON/USDT from multiple exchanges. When it detects an Alarm significantly deviating from the market price (which can be adjusted via `TICTON_THRESHOLD_PRICE` in `.evn` file for price deviation range), it performs arbitrage against it while also quoting to the Oracle.

If you want to understand the arbitrage mechanism of Tic Ton Oracle, you can refer to the following [2 Minute to Learn How TIC TON Oracle Works](https://www.youtube.com/watch?v=_EwAkiGiw-U&t=26s).

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
     - `TICTON_WALLET_MNEMONICS`: Your ton **testnet** wallet mnemonic, for example: a b c d e f g .....
     - `TICTON_ORACLE_ADDRESS`: The Address of ticton oracle (For this Competition2: kQCQPYxpFyFXxISiA_c42wNYrzcGc29NcFHqrupDTlT3a9It).
     - `TICTON_THRESHOLD_PRICE`: A float value sets a threshold for arbitrage bots to act on price differences. For instance, with TICTON_THRESHOLD_PRICE = 0.5, if Alarm 1's quote is 2.0 and TON's current quote is 2.5, arbitrage will be executed against Alarm 1.
     - `MY_ADDRESS`: Your ton **testnet** wallet address.

## Running the Application
1. **Docker Compose**: Navigate to the root directory of the project where the `docker-compose.yml` file is located.
2. **Start the Application**:
   - Run the following command:
     ```bash
     docker-compose up -d
     ```
  > [!WARNING]
  > This command will start all the services defined in your `docker-compose.yml` file.
  > Ensure that the `.env` file is correctly set up, as the Docker containers will rely on these environment variables.

3. **Check the Logs**:
   - Checking the current status of the bot will display the quotes received by the Oracle, show which Alarm IDs are available for arbitrage, and detail the arbitrage process.
     ```bash
     docker logs ticton-oracle-automation-app-1 -f
     ```
   - Below is the screen of it successfully running.
   ![succ](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/da80a97d-5f94-4195-b91d-af628f144094)
   - Below is the program receiving a new Tick message and related information about the quote.
   ![tick_new](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/e541e2f1-2363-4aa0-942c-0eee1c6e1191)

   - If the received quote from an Alarm exceeds the TICTON_THRESHOLD_PRICE, it will be placed into Profitable Alarms.
   ![tg_image_1169475916](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/0d2cd261-9b4b-4ff7-be78-1bf42c0de26f)

   - Execute the Wind operation.
     ![tg_image_986031882](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/f37243fa-f143-4631-ae1b-66aa488ca05f)
   - To determine whether the arbitrage was successful, you can check if the Timekeeper that received the Wind message is yourself.
     ![gogo09463415246_new](https://github.com/Ton-Dynasty/ticton-oracle-automation/assets/87699256/34ee52fa-3b41-4ae2-adb2-b04bcfae21d7)


5. **Stop the Application**:
     ```bash
     docker stop ticton-oracle-automation-app-1
     ```
6. **Restart the Application**:
   - It will start recording again from the Alarm information after the last checked Alarm ID when it was stoped.
     ```bash
     docker restart ticton-oracle-automation-app-1

## Completely Terminate the Application
```bash
docker compose down
docker system prune -a --volumes
rm -rf maria-db
```
     
## FAQ

### Common Errors
- `TonCenterException 429: Rate limit exceeded: 10 per 1 second` : If this issue arises, it's likely due to network latency. Resolve it by adding QPS ( float, 1~9 ), to the .env file to set the maximum requests per second. The default is 9; reducing the QPS can help.
- `TonCenterException 503`: This is normal. The problem happens because sometimes the toncenter API is not stable.
- `TonCenterException 500`: This is normal. This error message occurs when you wind or ring an alarm that no longer exists or has been fully arbitraged. It means you might be winding or ringing again, or someone else got there first.
