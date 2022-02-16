from typing import List
from algosdk.kmd import KMDClient

from ally.account import Account


def get_genesis_accounts(url: str, token: str) -> List[Account]:
    kmd = KMDClient(token, url)

    wallets = kmd.list_wallets()
    wallet_id = None
    for wallet in wallets:
        if wallet["name"] == "unencrypted-default-wallet":
            wallet_id = wallet["id"]
            break

    if wallet_id is None:
        raise Exception("Wallet not found: {}".format(
            "unencrypted-default-wallet"))

    wallet_handle = kmd.init_wallet_handle(wallet_id, "")

    try:
        addresses = kmd.list_keys(wallet_handle)
        private_keys = [
            kmd.export_key(wallet_handle, "", addr)
            for addr in addresses
        ]
        kmd_accounts = [Account(sk) for sk in private_keys]
    finally:
        kmd.release_wallet_handle(wallet_handle)

    return kmd_accounts
