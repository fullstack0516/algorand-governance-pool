import os

import dotenv

from ally.account import Account
from ally.operations import update_pool
from ally.utils import get_algod_client


if __name__ == '__main__':
    dotenv.load_dotenv(".env")

    client = get_algod_client(os.environ.get("ALGOD_URL"), os.environ.get("ALGOD_API_KEY"))

    governor1 = Account.from_mnemonic(os.environ.get("GOVERNOR1_MNEMONIC"))
    governor2 = Account.from_mnemonic(os.environ.get("GOVERNOR2_MNEMONIC"))
    governor3 = Account.from_mnemonic(os.environ.get("GOVERNOR3_MNEMONIC"))
    threshold = int(os.environ.get("MULTISIG_THRESHOLD"))
    
    governors = [governor1, governor2, governor3]

    app_id = int(os.environ.get("APP_ID"))
    
    update_pool(client, governors, threshold, app_id)
