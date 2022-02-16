import os

from pyteal import *

total_supply = 0xFFFFFFFFFFFFFFFF


class AllyPool:
    class Vars:
        gov_key = Bytes("gov")
        pool_token_key = Bytes("p")
        mint_price_key = Bytes("mp")
        redeem_price_key = Bytes("rp")
        commited_algos_key = Bytes("co")
        allow_redeem_key = Bytes("ar")

    @staticmethod
    @Subroutine(TealType.uint64)
    def mint_tokens(algos_in: TealType.uint64):
        # Mint in 1:1 with algos passed in
        mint_amount = WideRatio(
            [App.globalGet(AllyPool.Vars.mint_price_key), algos_in],
            [Int(1_000_000_000)]
        )
        return Seq(
            Return(mint_amount)
        )

    @staticmethod
    @Subroutine(TealType.uint64)
    def algos_to_redeem(amt: TealType.uint64):
        algos = WideRatio(
            [App.globalGet(AllyPool.Vars.redeem_price_key), amt],
            [Int(1_000_000_000)]
        )
        return Seq(
            Return(algos)
        )

    @staticmethod
    @Subroutine(TealType.none)
    def axfer(receiver: TealType.bytes, aid: TealType.uint64, amt: TealType.uint64):
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.AssetTransfer,
                    TxnField.xfer_asset: aid,
                    TxnField.asset_amount: amt,
                    TxnField.asset_receiver: receiver,
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    @staticmethod
    @Subroutine(TealType.none)
    def pay(receiver: TealType.bytes, amt: TealType.uint64):
        return Seq(
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields(
                {
                    TxnField.type_enum: TxnType.Payment,
                    TxnField.amount: amt,
                    TxnField.receiver: receiver
                }
            ),
            InnerTxnBuilder.Submit(),
        )

    def on_create(self):
        return Seq(
            App.globalPut(self.Vars.mint_price_key, Int(1_000_000_000)),
            App.globalPut(self.Vars.redeem_price_key, Int(1_000_000_000)),
            App.globalPut(self.Vars.allow_redeem_key, Int(1)),
            App.globalPut(self.Vars.commited_algos_key, Int(0)),
            App.globalPut(self.Vars.gov_key, Txn.sender()),
            Approve()
        )

    def on_bootstrap(self):
        pool_token_check = App.globalGetEx(Int(0), self.Vars.pool_token_key)
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            pool_token_check,
            # Make sure we've not already set this
            Assert(Not(pool_token_check.hasValue())),
            Assert(Txn.sender() == governor),
            # Create the pool token
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.AssetConfig,
                TxnField.config_asset_name: Bytes("wALGO"),
                TxnField.config_asset_unit_name: Bytes("wALGO"),
                TxnField.config_asset_url: Bytes("https://maxos.studio"),
                TxnField.config_asset_total: Int(total_supply),
                TxnField.config_asset_decimals: Int(6),
                TxnField.config_asset_manager: Global.zero_address(),
                TxnField.config_asset_reserve: Global.zero_address(),
                TxnField.config_asset_clawback: Global.zero_address(),
                TxnField.config_asset_freeze: Global.zero_address(),
            }),
            InnerTxnBuilder.Submit(),
            # Write it to global state
            App.globalPut(self.Vars.pool_token_key,
                          InnerTxn.created_asset_id()),
            Approve(),
        )

    def on_set_governor(self):
        new_gov = Txn.accounts[1]
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            Assert(Txn.sender() == governor),
            App.globalPut(self.Vars.gov_key, new_gov),
            Approve()
        )

    def on_set_mint_price(self):
        new_mint_price = Txn.application_args[1]
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            Assert(Txn.sender() == governor),
            App.globalPut(self.Vars.mint_price_key, Btoi(new_mint_price)),
            Approve()
        )

    def on_set_redeem_price(self):
        new_redeem_price = Txn.application_args[0]
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            Assert(Txn.sender() == governor),
            App.globalPut(self.Vars.redeem_price_key, Btoi(new_redeem_price)),
            Approve()
        )

    def on_toggle_redeem(self):
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            Assert(Txn.sender() == governor),
            App.globalPut(self.Vars.allow_redeem_key, Not(
                App.globalGet(self.Vars.allow_redeem_key))),
            Approve()
        )

    def on_join(self):
        governor = App.globalGet(self.Vars.gov_key)
        return Seq(
            Assert(
                And(
                    Txn.type_enum() == TxnType.ApplicationCall,
                    Txn.sender() == governor,
                )
            ),
            InnerTxnBuilder.Begin(),
            InnerTxnBuilder.SetFields({
                TxnField.type_enum: TxnType.Payment,
                TxnField.receiver: Txn.accounts[1],  # address of goverance
                TxnField.amount: Int(0),
                TxnField.note: Txn.application_args[
                    1
                ],  # expecting a valid note as the 2nd element in app args array
            }),
            InnerTxnBuilder.Submit(),
            Approve(),
        )

    def on_vote(self):
        algos_to_commit = Btoi(Txn.application_args[1])
        return Seq(
            # TODO:
            Approve(),
        )

    def on_mint(self):
        pool_token = App.globalGet(self.Vars.pool_token_key)
        pool_bal = AssetHolding.balance(
            Global.current_application_address(), pool_token)
        return Seq(
            # Init MaybeValues
            pool_bal,
            Assert(
                And(
                    Global.group_size() == Int(2),  # App call, Payment to mint
                    Gtxn[0].type_enum() == TxnType.ApplicationCall,
                    Gtxn[0].assets[0] == pool_token,
                    Gtxn[1].type_enum() == TxnType.Payment,
                    Gtxn[1].receiver() == Global.current_application_address(),
                    Gtxn[1].amount() > Int(1_000),
                    Gtxn[1].sender() == Gtxn[0].sender(),
                )
            ),
            self.axfer(
                Gtxn[0].sender(),
                pool_token,
                self.mint_tokens(Gtxn[1].amount() - Int(1_000))
            ),
            Approve(),
        )

    def on_redeem(self):
        pool_token = App.globalGet(self.Vars.pool_token_key)
        pool_bal = AssetHolding.balance(
            Global.current_application_address(), pool_token)
        return Seq(
            Assert(App.globalGet(self.Vars.allow_redeem_key)),
            Assert(
                And(
                    Global.group_size() == Int(2),
                    Gtxn[0].type_enum() == TxnType.ApplicationCall,
                    Gtxn[0].assets[0] == pool_token,
                    Gtxn[1].type_enum() == TxnType.AssetTransfer,
                    Gtxn[1].asset_receiver() == Global.current_application_address(),
                    Gtxn[1].xfer_asset() == pool_token,
                    Gtxn[0].sender() == Gtxn[1].sender(),
                )
            ),
            pool_bal,
            self.pay(Gtxn[1].sender(), self.algos_to_redeem(Gtxn[1].asset_amount())),
            Approve(),
        )

    def on_call(self):
        on_call_method = Txn.application_args[0]
        return Cond(
            # Admin
            [on_call_method == Bytes("bootstrap"), self.on_bootstrap()],
            [on_call_method == Bytes("set_governor"), self.on_set_governor()],
            [on_call_method == Bytes("set_mint_price"),
             self.on_set_mint_price()],
            [on_call_method == Bytes("set_redeem_price"),
             self.on_set_redeem_price()],
            [on_call_method == Bytes("toggle_redeem"),
             self.on_toggle_redeem()],
            [on_call_method == Bytes("join"), self.on_join()],
            [on_call_method == Bytes("vote"), self.on_vote()],
            # Users
            [on_call_method == Bytes("mint"), self.on_mint()],
            [on_call_method == Bytes("redeem"), self.on_redeem()],
        )

    def approval_program(self):
        governor = App.globalGet(self.Vars.gov_key)
        program = Cond(
            [Txn.application_id() == Int(0), self.on_create()],
            [
                Txn.on_completion() == OnComplete.DeleteApplication,
                Return(Txn.sender() == governor)
            ],
            [
                Txn.on_completion() == OnComplete.UpdateApplication,
                Return(Txn.sender() == governor)
            ],
            [Txn.on_completion() == OnComplete.CloseOut, Approve()],
            [Txn.on_completion() == OnComplete.OptIn, Reject()],
            [Txn.on_completion() == OnComplete.NoOp, self.on_call()],
        )
        return program

    def clear_program(self):
        return Approve()


if __name__ == "__main__":
    path = os.path.dirname(os.path.abspath(__file__))
    pool = AllyPool()
    with open(os.path.join(path, "approval.teal"), "w") as f:
        compiled = compileTeal(pool.approval_program(),
                               mode=Mode.Application, version=5)
        f.write(compiled)

    with open(os.path.join(path, "clear.teal"), "w") as f:
        compiled = compileTeal(pool.clear_program(),
                               mode=Mode.Application, version=5)
        f.write(compiled)
