import os

import dotenv

from ally.account import Account
from ally.operations import redeem_walgo
from ally.utils import get_algod_client, get_balances
    

if __name__ == '__main__':
    dotenv.load_dotenv(".env")

    client = get_algod_client(os.environ.get("ALGOD_URL"), os.environ.get("ALGOD_API_KEY"))

    minter = Account.from_mnemonic(os.environ.get("MINTER_MNEMONIC"))
    print(f"minter: {minter.get_address()}")

    app_id = int(os.environ.get("APP_ID"))
    walgo_id = int(os.environ.get("WALGO_ID"))
    amount = 1_000_000
    
    redeem_walgo(client, minter, app_id, walgo_id, amount)
    
    print(get_balances(client, minter.get_address()))
