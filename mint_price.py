import sys
import os
import dotenv

from typing import List
from algosdk import encoding
from ally.account import Account
from ally.operations import set_mint_price
from ally.utils import get_algod_client, get_app_global_state
from algosdk.future import transaction

ALLOWED_SHIFT = 2.5 # percent

MIN = 1 - ALLOWED_SHIFT/100
MAX = 1 + ALLOWED_SHIFT/100

if __name__ == '__main__':
    dotenv.load_dotenv('.env')

    client = get_algod_client(os.environ.get("ALGOD_URL"), os.environ.get("ALGOD_API_KEY"))
    app_id = int(os.environ.get("APP_ID"))
    version = 1
    threshold = int(os.environ.get("MULTISIG_THRESHOLD"))
    
    governor1 = Account.from_mnemonic(os.environ.get("GOVERNOR1_MNEMONIC"))
    governor2 = Account.from_mnemonic(os.environ.get("GOVERNOR2_MNEMONIC"))
    governor3 = Account.from_mnemonic(os.environ.get("GOVERNOR3_MNEMONIC"))
    governors = [governor1, governor2, governor3]

    state = get_app_global_state(client, app_id)
    current_mint_price = state[b"mp"]

    if len(sys.argv) >= 2 and sys.argv[1] == "--get":
        state = get_app_global_state(client, app_id)
        current_mint_price = state[b"mp"]
        print(current_mint_price)
    elif len(sys.argv) >= 3 and sys.argv[1] == "--set":
        new_mint_price = int(sys.argv[2])
        shift = (new_mint_price/current_mint_price)

        if shift == 1:
            print("mint price is unchanged")
        elif (shift >= MIN and shift <= MAX) or (len(sys.argv) >= 4 and sys.argv[3] == "--force"):
            set_mint_price(new_mint_price, client, governors, app_id, version, threshold)
        else:
            print("the shift when setting the mint value should not be greater than 2.5%")
            print("if you meant this, add --force at the end of the command")
    else:
        print("available actions:")
        print("\t--get \t\treturns the current mint price")
        print("\t--set VALUE \tsets the mint price to the given value")
    