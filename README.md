# Ticton Oracle Bot

## Overview
The **Ticton Oracle Bot** is an arbitrage bot that operates by fetching the average market price of TON/USDT from multiple exchanges. It then quotes this price to the Ticton Oracle. In doing so, it seeks arbitrage opportunities among other quoters. 

## Prerequisites
- Docker
- Docker Compose

## Setting Up the Environment
1. **Clone the Repository**: Clone this repository to your local machine.

2. **Environment Variables**: 
   - Create a `.env` file in the root directory of the project.
   - Fill out your `.env` file using `.env.example` as a guide.
   - Obtain your Ton Center Testnet API key from [@tonapibot](https://t.me/tonapibot)

## Running the Application
1. **Docker Compose**: Navigate to the root directory of the project where the `docker-compose.yml` file is located.
2. **Start the Application**:
   - Run the following command:
     ```
     docker-compose up -d
     ```
   - This command will start all the services defined in your `docker-compose.yml` file.
   - Ensure that the `.env` file is correctly set up, as the Docker containers will rely on these environment variables.

