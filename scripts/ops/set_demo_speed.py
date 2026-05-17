"""
Set demo_multiplier = 10 on the deployed T-Bill contract.
10 seconds per "day" means 1-day T-Bill matures in 10 seconds.
No redeployment needed — uses the built-in set_demo_mode admin method.
"""

import algosdk
from algosdk.v2client import algod
from algosdk import transaction
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    AccountTransactionSigner,
    TransactionWithSigner,
)
from algosdk.abi import Method, Contract
import base64, json

ALGOD_URL   = "https://testnet-api.algonode.cloud"
TBILL_APP   = 762214340
DEPLOYER_MNEMONIC = (
    "blossom artwork cactus reject sick vacuum august will victory donkey common "
    "essay spice source syrup approve quiz world replace journey piece world pyramid "
    "abstract slice"
)

NEW_DEMO_MULTIPLIER = 10   # 10 seconds per "day"  →  1-day matures in 10s
DEMO_MODE_ENABLED   = 1    # keep demo mode on

def main():
    client = algod.AlgodClient("", ALGOD_URL)
    private_key = algosdk.mnemonic.to_private_key(DEPLOYER_MNEMONIC)
    sender      = algosdk.account.address_from_private_key(private_key)
    signer      = AccountTransactionSigner(private_key)

    print(f"Deployer : {sender}")
    print(f"App ID   : {TBILL_APP}")

    # Read current value
    info = client.application_info(TBILL_APP)
    for item in info["params"]["global-state"]:
        key = base64.b64decode(item["key"]).decode("utf-8", errors="replace")
        if key == "demo_multiplier":
            print(f"Current demo_multiplier = {item['value']['uint']}")

    sp = client.suggested_params()
    sp.flat_fee = True
    sp.fee = 1000

    # ABI: set_demo_mode(uint64,uint64)void
    method = Method.from_signature("set_demo_mode(uint64,uint64)void")

    atc = AtomicTransactionComposer()
    atc.add_method_call(
        app_id=TBILL_APP,
        method=method,
        sender=sender,
        sp=sp,
        signer=signer,
        method_args=[DEMO_MODE_ENABLED, NEW_DEMO_MULTIPLIER],
    )

    result = atc.execute(client, 4)
    print(f"TX ID    : {result.tx_ids[0]}")
    print(f"Done: demo_multiplier set to {NEW_DEMO_MULTIPLIER}")
    print(f"1-day T-Bill now matures in {NEW_DEMO_MULTIPLIER} seconds.")

if __name__ == "__main__":
    main()
