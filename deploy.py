import os
import dotenv

from algosdk.logic import get_application_address
from algosdk.future import transaction

from ally.operations import bootstrap_pool, create_pool
from ally.utils import get_algod_client, get_app_global_state, get_balances, wait_for_transaction
from ally.account import Account


if __name__ == '__main__':
    dotenv.load_dotenv(".env")

    client = get_algod_client(os.environ.get("ALGOD_URL"), os.environ.get("ALGOD_API_KEY"))

    governor1 = Account.from_mnemonic(os.environ.get("GOVERNOR1_MNEMONIC"))
    governor2 = Account.from_mnemonic(os.environ.get("GOVERNOR2_MNEMONIC"))
    governor3 = Account.from_mnemonic(os.environ.get("GOVERNOR3_MNEMONIC"))
    threshold = int(os.environ.get("MULTISIG_THRESHOLD"))
    governors = [governor1, governor2, governor3]
    
    funder = Account.from_mnemonic(os.environ.get("FUNDER_MNEMONIC"))
    
    msig = transaction.Multisig(1, threshold, [governor.get_address() for governor in governors])
    
    if get_balances(client, msig.address())[0] < 2_713_000:
        pay_txn = transaction.PaymentTxn(
            sender=funder.get_address(),
            sp=client.suggested_params(),
            receiver=msig.address(),
            amt=2_713_000
        )
        signed_pay_txn = pay_txn.sign(funder.get_private_key())
        client.send_transaction(signed_pay_txn)
        wait_for_transaction(client, pay_txn.get_txid())

    app_id = create_pool(client, governors, threshold)

    print(f"App ID: {app_id}")
    print(f"App address: {get_application_address(app_id)}")
    
    if get_balances(client, get_application_address(app_id))[0] < 202_000:
        pay_txn = transaction.PaymentTxn(
            sender=funder.get_address(),
            sp=client.suggested_params(),
            receiver=get_application_address(app_id),
            amt=202_000
        )
        signed_pay_txn = pay_txn.sign(funder.get_private_key())
        client.send_transaction(signed_pay_txn)
        wait_for_transaction(client, pay_txn.get_txid())
    
    bootstrap_pool(client, governors, threshold, app_id)
    
    state = get_app_global_state(client, app_id)
    
    print("Global state: ", state)
