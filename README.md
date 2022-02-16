# Ally for Algorand Governance

- Install Docker and Docker-Compose.

- Setup Environment

```
python3 -m venv venv
source venv/bin/activate
```

- Install Dependencies
```
pip install -r requirements.txt
```

First, start an instance of sandbox (requires Docker):

```
./sandbox up
```

When finished, the sandbox can be stopped with: 

```
./sandbox down
```

Before running commands you have to create the .env file based on the .env.example

In order to get the MNEMONICS for 3 governors, 1 funder and 1 minter, run:

```
python local_setup.py
```

and fill the governors, minter and funder mnemonics from that command's output

this only works as a shortcut for the local sandbox, when using testnets or mainnet
you need to create accounts manually on AlgoSigner.

also the MULTISIG_THRESHOLD should be filled with a number

- Deploy contract and create pool token

```
python deploy.py
```

- The deployment returns an APP_ID that you have to insert in the .env file to interact with the contract
using the redeem_walgo.py, set_governor.py, update_pool.py, mint_walgo.py scripts 


- Destroy contract

```
python destroy.py
```

- Set governor 

```
python set_governor.py
```