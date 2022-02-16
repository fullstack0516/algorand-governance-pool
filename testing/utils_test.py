import os
import dotenv
import base64

from algosdk.v2client.algod import AlgodClient
from algosdk.kmd import KMDClient
from algosdk import encoding

from ally.utils import get_algod_client, get_kmd_client, get_genesis_accounts

dotenv.load_dotenv(".env")

def test_get_algod_client():
    client = get_algod_client(os.environ.get("ALGOD_URL"), os.environ.get("ALGOD_API_KEY"))
    assert isinstance(client, AlgodClient)

    response = client.health()
    assert response is None


def test_get_kmd_client():
    kmd = get_kmd_client(os.environ.get("KMD_ADDRESS"), os.environ.get("KMD_TOKEN"))
    assert isinstance(kmd, KMDClient)

    response = kmd.versions()
    expected = ["v1"]
    assert response == expected


def test_get_genesis_accounts():
    kmd = get_kmd_client(os.environ.get("KMD_ADDRESS"), os.environ.get("KMD_TOKEN"))

    accounts = get_genesis_accounts(kmd)

    assert len(accounts) == 3
    assert all(encoding.is_valid_address(account.get_address()) for account in accounts)
    assert all(
        len(base64.b64decode(account.get_private_key())) == 64 for account in accounts
    )
