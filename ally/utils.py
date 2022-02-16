from base64 import b64decode
from typing import Dict, Union, List, Any, Optional

from algosdk import encoding
from algosdk.v2client.algod import AlgodClient
from algosdk.kmd import KMDClient
from pyteal import compileTeal, Expr, Mode

from .account import Account


def get_algod_client(url, token) -> AlgodClient:
    headers = {
        'X-API-Key': token
    }
    return AlgodClient(token, url, headers)

def get_kmd_client(url, token) -> KMDClient:
    return KMDClient(token, url)

class PendingTxnResponse:
    def __init__(self, response: Dict[str, Any]) -> None:
        self.poolError: str = response["pool-error"]
        self.txn: Dict[str, Any] = response["txn"]

        self.application_index: Optional[int] = response.get(
            "application-index")
        self.asset_index: Optional[int] = response.get("asset-index")
        self.close_rewards: Optional[int] = response.get("close-rewards")
        self.closing_amount: Optional[int] = response.get("closing-amount")
        self.confirmed_round: Optional[int] = response.get("confirmed-round")
        self.global_state_delta: Optional[Any] = response.get(
            "global-state-delta")
        self.local_state_delta: Optional[Any] = response.get(
            "local-state-delta")
        self.receiver_rewards: Optional[int] = response.get("receiver-rewards")
        self.sender_rewards: Optional[int] = response.get("sender-rewards")

        self.inner_txns: List[Any] = response.get("inner-txns", [])
        self.logs: List[bytes] = [b64decode(ll)
                                  for ll in response.get("logs", [])]


def wait_for_transaction(
        client: AlgodClient, tx_id: str
) -> PendingTxnResponse:
    last_status = client.status()
    last_round = last_status.get("last-round")
    pending_txn = client.pending_transaction_info(tx_id)
    while not (pending_txn.get("confirmed-round") and pending_txn.get("confirmed-round") > 0):
        print("Waiting for confirmation...")
        last_round += 1
        client.status_after_block(last_round)
        pending_txn = client.pending_transaction_info(tx_id)
    print(
        "Transaction {} confirmed in round {}.".format(
            tx_id, pending_txn.get("confirmed-round")
        )
    )
    return PendingTxnResponse(pending_txn)


def fully_compile_contract(client: AlgodClient, contract: Expr) -> bytes:
    teal = compileTeal(contract, mode=Mode.Application, version=5)
    response = client.compile(teal)
    return b64decode(response["result"])


def decode_state(state_array: List[Any]) -> Dict[bytes, Union[int, bytes]]:
    state: Dict[bytes, Union[int, bytes]] = dict()

    for pair in state_array:
        key = b64decode(pair["key"])

        value = pair["value"]
        value_type = value["type"]

        if value_type == 2:
            # value is uint64
            value = value.get("uint", 0)
        elif value_type == 1:
            # value is byte array
            value = b64decode(value.get("bytes", ""))
        else:
            raise Exception(f"Unexpected state type: {value_type}")

        state[key] = value

    return state


def get_app_global_state(
        client: AlgodClient, app_id: int
) -> Dict[bytes, Union[int, bytes]]:
    app_info = client.application_info(app_id)
    return decode_state(app_info["params"]["global-state"])


def get_app_local_state(
        client: AlgodClient, app_id: int, sender: Account
) -> Dict[bytes, Union[int, bytes]]:
    account_info = client.account_info(sender.get_address())
    for local_state in account_info["apps-local-state"]:
        if local_state["id"] == app_id:
            if "key-value" not in local_state:
                return {}

            return decode_state(local_state["key-value"])
    return {}


def get_app_address(app_id: int) -> str:
    to_hash = b"appID" + app_id.to_bytes(8, "big")
    return encoding.encode_address(encoding.checksum(to_hash))


def get_balances(client: AlgodClient, account: str) -> Dict[int, int]:
    balances: Dict[int, int] = dict()

    account_info = client.account_info(account)

    # set key 0 to Algo balance
    balances[0] = account_info["amount"]

    assets: List[Dict[str, Any]] = account_info.get("assets", [])
    for assetHolding in assets:
        asset_id = assetHolding["asset-id"]
        amount = assetHolding["amount"]
        balances[asset_id] = amount

    return balances


def get_genesis_accounts(kmd: KMDClient) -> List[Account]:
    wallets = kmd.list_wallets()
    walletID = None
    for wallet in wallets:
        if wallet["name"] == "unencrypted-default-wallet":
            walletID = wallet["id"]
            break

    if walletID is None:
        raise Exception("Wallet not found: {}".format(
            "unencrypted-default-wallet"))

    walletHandle = kmd.init_wallet_handle(walletID, "")

    try:
        addresses = kmd.list_keys(walletHandle)
        privateKeys = [
            kmd.export_key(walletHandle, "", addr)
            for addr in addresses
        ]
        kmdAccounts = [Account(sk) for sk in privateKeys]
    finally:
        kmd.release_wallet_handle(walletHandle)

    return kmdAccounts


def is_opted_in_asset(client: AlgodClient, asset_id: int, addr: str):
    account_info = client.account_info(addr)  
    for a in account_info.get('assets', []):
        if a['asset-id'] == asset_id:
            return True
    return False
