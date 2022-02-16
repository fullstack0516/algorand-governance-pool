import random
from base64 import b64decode
from typing import List, Tuple
from algosdk.v2client.algod import AlgodClient
from algosdk.future import transaction
from algosdk.logic import get_application_address
from algosdk import encoding
from pyteal import compileTeal, Mode

from .utils import get_balances, is_opted_in_asset, wait_for_transaction
from .account import Account
from .contracts.pool import AllyPool


def fullyCompileContract(client: AlgodClient, teal: str) -> bytes:
    response = client.compile(teal)
    return b64decode(response["result"])


def get_contracts(client: AlgodClient) -> Tuple[bytes, bytes]:
    pool = AllyPool()
    approval_program = fullyCompileContract(
        client, compileTeal(pool.approval_program(), mode=Mode.Application, version=5)
    )
    clear_state_program = fullyCompileContract(
        client, compileTeal(pool.clear_program(), mode=Mode.Application, version=5)
    )

    return approval_program, clear_state_program


def create_pool(client: AlgodClient, governors: List[Account], multisig_threshold: int):
    """Create a pool.

    Args:
        client: An algod client.
        governors: governor accounts list.
        multisig_threshold: multi signature threshold.
    Returns:
        The ID of the newly created pool.
    """
    approval, clear = get_contracts(client)
    global_schema = transaction.StateSchema(num_uints=32, num_byte_slices=32)
    local_schema = transaction.StateSchema(num_uints=0, num_byte_slices=0)
    
    msig = transaction.Multisig(
        1, multisig_threshold, 
        [governor.get_address() for governor in governors]
    )

    txn = transaction.ApplicationCreateTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        on_complete=transaction.OnComplete.NoOpOC,
        approval_program=approval,
        clear_program=clear,
        global_schema=global_schema,
        local_schema=local_schema,
    )
    mtx = transaction.MultisigTransaction(txn, msig)
    
    idxs = random.sample(range(0, len(governors)), multisig_threshold)
    for idx in idxs:
        mtx.sign(governors[idx].get_private_key())
    
    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))

    response = wait_for_transaction(client, tx_id)
    assert response.application_index is not None and response.application_index > 0
    return response.application_index


def bootstrap_pool(client: AlgodClient, governors: List[Account], multisig_threshold: int, app_id: int):
    """Initialize a pool configuration.

    Args:
        client: An algod client.
        governors: governor accounts list.
        multisig_threshold: multi signature threshold.
        app_id: application ID.
    """
    msig = transaction.Multisig(
        1, multisig_threshold, 
        [governor.get_address() for governor in governors]
    )
    print(f"Sender: {msig.address()}")

    txn = transaction.ApplicationCallTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"bootstrap"],
    )
    mtx = transaction.MultisigTransaction(txn, msig)
    
    signers = random.choices(governors, k=multisig_threshold)
    for signer in signers:
        mtx.sign(signer.get_private_key())
    
    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))
    
    wait_for_transaction(client, tx_id)
    
    
def set_governor(client: AlgodClient, sender: Account, app_id: int, governors: List[Account], version: int, threshold: int):
    """Initialize governor configuration.

    Args:
        client: An algod client.
        sender: Sender account.
        app_id: Application ID.
        governors: governor accounts list.
        version: Version.
        threshold: threshold.
    """
    msig = transaction.Multisig(
        version, threshold, [governor.get_address() for governor in governors]
    )

    print('multisig address: ', msig.address())

    txn = transaction.ApplicationCallTxn(
        sender=sender.get_address(),
        sp=client.suggested_params(),
        index=app_id,
        app_args=[b"set_governor"],
        accounts=[msig.address()],
        on_complete=transaction.OnComplete.NoOpOC
    )
    signed_txn = txn.sign(sender.get_private_key())

    client.send_transaction(signed_txn)

    wait_for_transaction(client, signed_txn.get_txid())
    
    
def destroy_pool(client: AlgodClient, governors: List[Account], multisig_threshold: int, app_id: int):
    """Destroy pool.

    Args:
        client: An algod client.
        governors: governor accounts list.
        multisig_threshold: multi signature threshold.
        app_id: Application ID.
    """
    msig = transaction.Multisig(
        1, multisig_threshold, 
        [governor.get_address() for governor in governors]
    )
    print(f"Sender: {msig.address()}")
    
    txn = transaction.ApplicationDeleteTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        index=app_id
    )
    mtx = transaction.MultisigTransaction(txn, msig)
    
    idxs = random.sample(range(0, len(governors)), multisig_threshold)
    for idx in idxs:
        mtx.sign(governors[idx].get_private_key())
    
    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))
    
    wait_for_transaction(client, tx_id)
    

def update_pool(client: AlgodClient, governors: List[Account], multisig_threshold: int, app_id: int):
    """Update pool.

    Args:
        client: An algod client.
        governors: governor accounts list.
        multisig_threshold: multi signature threshold.
        app_id: Application ID.
    """
    approval, clear = get_contracts(client)
    msig = transaction.Multisig(
        1, multisig_threshold, 
        [governor.get_address() for governor in governors]
    )
    print(f"Sender: {msig.address()}")
    txn = transaction.ApplicationUpdateTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        index=app_id,
        approval_program=approval,
        clear_program=clear
    )
    mtx = transaction.MultisigTransaction(txn, msig)
    
    idxs = random.sample(range(0, len(governors)), multisig_threshold)
    for idx in idxs:
        mtx.sign(governors[idx].get_private_key())
    
    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))
    
    wait_for_transaction(client, tx_id)
    
    
def mint_walgo(client: AlgodClient, sender: Account, app_id: int, asset_id: int, amount: int):
    """Mint walgo.

    Args:
        client: An algod client.
        sender: Sender Account.
        app_id: Application ID.
        asset_id: Asset ID.
        amount: Number of walgo.
    """

    if not is_opted_in_asset(client, asset_id, sender.get_address()):
        txn = transaction.AssetOptInTxn(
            sender=sender.get_address(),
            sp=client.suggested_params(),
            index=asset_id
        )
        signed_txn = txn.sign(sender.get_private_key())
        client.send_transaction(signed_txn)
        
        wait_for_transaction(client, txn.get_txid())
        
    call_txn = transaction.ApplicationCallTxn(
        sender=sender.get_address(),
        sp=client.suggested_params(),
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"mint"],
        foreign_assets=[asset_id]
    )
    payment_txn = transaction.PaymentTxn(
        sender=sender.get_address(),
        sp=client.suggested_params(),
        receiver=get_application_address(app_id),
        amt=amount + 1_000
    )
    
    transaction.assign_group_id([call_txn, payment_txn])
    
    signed_call_txn = call_txn.sign(sender.get_private_key())
    signed_payment_txn = payment_txn.sign(sender.get_private_key())
    
    tx_id = client.send_transactions([signed_call_txn, signed_payment_txn])
    
    wait_for_transaction(client, tx_id)
    
    
def redeem_walgo(client: AlgodClient, sender: Account, app_id: int, asset_id: int, amount: int):
    """Redeem walgo.

    Args:
        client: An algod client.
        sender: Sender Account.
        app_id: Application ID.
        asset_id: Asset ID.
        amount: Number of walgo.
    """

    call_txn = transaction.ApplicationCallTxn(
        sender=sender.get_address(),
        sp=client.suggested_params(),
        index=app_id,
        on_complete=transaction.OnComplete.NoOpOC,
        app_args=[b"redeem"],
        foreign_assets=[asset_id]
    )
    axfer_txn = transaction.AssetTransferTxn(
        sender=sender.get_address(),
        sp=client.suggested_params(),
        receiver=get_application_address(app_id),
        amt=amount,
        index=asset_id
    )
    
    transaction.assign_group_id([call_txn, axfer_txn])
    
    signed_call_txn = call_txn.sign(sender.get_private_key())
    signed_axfer_txn = axfer_txn.sign(sender.get_private_key())
    
    tx_id = client.send_transactions([signed_call_txn, signed_axfer_txn])
    
    wait_for_transaction(client, tx_id)


def toggle_redeem(client: AlgodClient, governors: List[Account], app_id: int, version: int, multisig_threshold: int):
    """Toggle redeem.

    Args:
        client: An algod client.
        governors: governor accounts list.
        app_id: Application ID.
        version: Version.
        multisig_threshold: multi signature threshold.
    """
    msig = transaction.Multisig(
        1, multisig_threshold,
        [governor.get_address() for governor in governors]
    )

    txn = transaction.ApplicationCallTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        index=app_id,
        app_args=["toggle_redeem"],
        on_complete=transaction.OnComplete.NoOpOC
    )

    mtx = transaction.MultisigTransaction(txn, msig)

    print(f"Sender: {msig.address()}")

    idxs = random.sample(range(0, len(governors)), multisig_threshold)
    for idx in idxs:
        mtx.sign(governors[idx].get_private_key())

    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))

    wait_for_transaction(client, tx_id)
    

def set_mint_price(mint_price: int, client: AlgodClient, governors: List[Account], app_id: int, version: int, multisig_threshold: int):
    """Set mint price.

    Args:
        mint_price: Mint price.
        client: An algod client.
        governors: governor accounts list.
        app_id: Application ID.
        version: Version.
        multisig_threshold: multi signature threshold.
    """    
    msig = transaction.Multisig(
        1, multisig_threshold,
        [governor.get_address() for governor in governors]
    )

    txn = transaction.ApplicationCallTxn(
        sender=msig.address(),
        sp=client.suggested_params(),
        index=app_id,
        app_args=["set_mint_price", mint_price.to_bytes(8, 'big')],
        on_complete=transaction.OnComplete.NoOpOC
    )

    mtx = transaction.MultisigTransaction(txn, msig)

    print(f"Sender: {msig.address()}")

    idxs = random.sample(range(0, len(governors)), multisig_threshold)
    for idx in idxs:
        mtx.sign(governors[idx].get_private_key())

    tx_id = client.send_raw_transaction(encoding.msgpack_encode(mtx))

    wait_for_transaction(client, tx_id)

