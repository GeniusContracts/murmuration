# Fungible Assets - FA12
# Inspired by https://gitlab.com/tzip/tzip/blob/master/A/FA1.2.md

# This file is copied verbatim from http://smartpy.io/dev/?template=fa12.py on 23/02/2021.
# All changed lines are annotated with `CHANGED: <description>`

# This contract is based largely off of Compound's COMP token:
# https://github.com/compound-finance/compound-protocol/blob/master/contracts/Governance/Comp.sol

import smartpy as sp

FA2_test = sp.io.import_script_from_url("file:test-helpers/fa2.py")
Addresses = sp.io.import_script_from_url("file:test-helpers/addresses.py")
Errors = sp.io.import_script_from_url("file:common/errors.py")

# CHANGED: Compress the contract into a single entity, rather than using inheritance.
class EscrowSDAO(sp.Contract):
    def __init__(
        self, 
        # CHANGED: Give admin a default value
        tokenContractAddress = Addresses.TOKEN_ADMIN_ADDRESS,
        tokenID = sp.nat(0)
    ):
        # CHANGED: Construct token metadata.
        metadata_data = sp.utils.bytes_of_string('{ "name": "SalsaDAO Escrow", "description": "Locking contract for governance", "authors": ["Genius Contracts"], "homepage":  "https://salsadao.xyz" }')

        metadata = sp.big_map(
            l = {
                "": sp.bytes('0x74657a6f732d73746f726167653a64617461'), # "tezos-storage:data"
                "data": metadata_data
            },
            tkey = sp.TString,
            tvalue = sp.TBytes            
        )


        self.init(
            tokenContractAddress = tokenContractAddress,
            tokenID = tokenID,
            balances = sp.big_map(
                tkey = sp.TAddress,
                tvalue = sp.TNat,
            ),

            # CHANGED: Add Checkpoints
            checkpoints = sp.big_map(
                l = {},
                tkey = sp.TPair(sp.TAddress, sp.TNat),
                tvalue = sp.TRecord(fromBlock = sp.TNat, balance = sp.TNat).layout(("fromBlock", "balance"))
            ),
            # CHANGED: Add numCheckpoints
            numCheckpoints = sp.big_map(
                l = {},
                tkey = sp.TAddress,
                tvalue = sp.TNat
            ),

            # CHANGED: Include metadata and token_metadata bigmap in storage.
            metadata = metadata,
        )
        
    # CHANGED: Add method to write checkpoints.
    @sp.sub_entry_point
    def writeCheckpoint(self, params):
        sp.set_type(params, sp.TRecord(checkpointedAddress = sp.TAddress, numCheckpoints = sp.TNat, newBalance = sp.TNat).layout(("checkpointedAddress", ("numCheckpoints", "newBalance"))))

        # If there are no checkpoints, write data.
        sp.if params.numCheckpoints == 0:
            self.data.checkpoints[(params.checkpointedAddress, 0)] = sp.record(fromBlock = sp.level, balance = params.newBalance)
            self.data.numCheckpoints[params.checkpointedAddress] = params.numCheckpoints + 1
        sp.else:
            # Otherwise, if this update occurred in the same block, overwrite
            sp.if self.data.checkpoints[(params.checkpointedAddress, sp.as_nat(params.numCheckpoints - 1))].fromBlock == sp.level: 
                self.data.checkpoints[(params.checkpointedAddress, sp.as_nat(params.numCheckpoints - 1))] = sp.record(fromBlock = sp.level, balance = params.newBalance)
            sp.else:
                # Only write an additional checkpoint if the balance has changed.
                sp.if self.data.checkpoints[(params.checkpointedAddress, sp.as_nat(params.numCheckpoints - 1))].balance != params.newBalance:
                    self.data.checkpoints[(params.checkpointedAddress, params.numCheckpoints)] = sp.record(fromBlock = sp.level, balance = params.newBalance)
                    self.data.numCheckpoints[params.checkpointedAddress] = params.numCheckpoints + 1
      
    # CHANGED: Add view to get balance from checkpoints
    @sp.utils.view(sp.TRecord(address = sp.TAddress, level = sp.TNat, result = sp.TNat))
    def getPriorBalance(self, params):
        sp.set_type(params, sp.TRecord(
            address = sp.TAddress,
            level = sp.TNat,
        ).layout(("address", "level")))

        sp.verify(params.level < sp.level, Errors.ERROR_BLOCK_LEVEL_TOO_SOON)

        # If there are no checkpoints, return 0.
        sp.if self.data.numCheckpoints.get(params.address, 0) == 0:
            sp.result(sp.record(result = 0, address = params.address, level = params.level))
        sp.else:
            # First check most recent balance.
            sp.if self.data.checkpoints[(params.address, sp.as_nat(self.data.numCheckpoints[params.address] - 1))].fromBlock <= params.level:
                sp.result(sp.record(
                    result = self.data.checkpoints[(params.address, sp.as_nat(self.data.numCheckpoints[params.address] - 1))].balance,
                    address = params.address,
                    level = params.level
                ))
            sp.else:
                # Next, check for an implicit zero balance.
                sp.if self.data.checkpoints[(params.address, sp.nat(0))].fromBlock > params.level:
                    sp.result(sp.record(result = 0, address = params.address, level = params.level))
                sp.else:
                    # A boolean that indicates that the current center is the level we are looking for.
                    # This extra variable is required because SmartPy does not have a way to break from
                    # a while loop. 
                    centerIsNeedle = sp.local('centerIsNeedle', False)

                    # Otherwise perform a binary search.
                    center = sp.local('center', 0)
                    lower = sp.local('lower', 0)
                    upper = sp.local('upper', sp.as_nat(self.data.numCheckpoints[params.address] - 1))   
                                        
                    sp.while (upper.value > lower.value) & (centerIsNeedle.value == False):
                        # A complicated way to get the ceiling.
                        center.value = sp.as_nat(upper.value - (sp.as_nat(upper.value - lower.value) / 2))
                        
                        # Check that center is the exact block we are looking for.
                        sp.if self.data.checkpoints[(params.address, center.value)].fromBlock == params.level:
                            centerIsNeedle.value = True
                        sp.else:
                            sp.if self.data.checkpoints[(params.address, center.value)].fromBlock < params.level:
                                lower.value = center.value
                            sp.else:
                                upper.value = sp.as_nat(center.value - 1)

                    # If the center is the needle, return the value at center.
                    sp.if centerIsNeedle.value == True:
                        sp.result(
                            sp.record(
                                result = self.data.checkpoints[(params.address, center.value)].balance,
                                address = params.address, 
                                level = params.level
                            )
                        )
                    # Otherwise return the result.
                    sp.else:
                        sp.result(
                            sp.record(
                                result = self.data.checkpoints[(params.address, lower.value)].balance, 
                                address = params.address, 
                                level = params.level
                            )
                        )

    def addAddressIfNecessary(self, address):
        sp.if ~ self.data.balances.contains(address):
            self.data.balances[address] = 0

    @sp.utils.view(sp.TNat)
    def getBalance(self, params):
        # CHANGED: Add address if needed.
        self.addAddressIfNecessary(params)

        sp.result(self.data.balances[params])

    @sp.entry_point
    def escrow(self, params):
        sp.set_type(params, sp.TRecord(
            value = sp.TNat,
            )
        ).layout("value")

        # Verify the requester is the governor.
        # sp.verify(sp.sender == self.data.governorAddress, Errors.ERROR_NOT_GOVERNOR)

        # Transfer the sDAO
        handle = sp.contract(
            sp.TList(
                sp.TRecord(
                    from_ = sp.TAddress,
                    txs = sp.TList(
                        sp.TRecord(
                            amount = sp.TNat,
                            to_ = sp.TAddress, 
                            token_id = sp.TNat,
                        ).layout(("to_", ("token_id", "amount")))
                    )
                ).layout(("from_", "txs"))
            ),
            self.data.tokenContractAddress,
            "transfer"
        ).open_some()

        arg = [
            sp.record(
                from_ = sp.sender,
                txs = [
                    sp.record(
                        amount = params.value,
                        to_ = sp.self_address,
                        token_id = self.data.tokenID
                    )
                ]
            )
        ]
        sp.transfer(arg, sp.mutez(0), handle)

        self.addAddressIfNecessary(sp.sender)
        self.data.balances[sp.sender] += params.value
        
        # CHANGED
        # Write a checkpoint for the receiver
        self.writeCheckpoint(
            sp.record(
                checkpointedAddress = sp.sender,
                numCheckpoints = self.data.numCheckpoints.get(sp.sender, 0),
                newBalance = self.data.balances[sp.sender]
            )
        )

    @sp.entry_point
    def release(self, params):
        sp.set_type(params, sp.TRecord(
            value = sp.TNat,
            )
        ).layout("value")

        # Verify the requester is the governor.

        # Transfer the sDAO
        handle = sp.contract(
            sp.TList(
                sp.TRecord(
                    from_ = sp.TAddress,
                    txs = sp.TList(
                        sp.TRecord(
                            amount = sp.TNat,
                            to_ = sp.TAddress, 
                            token_id = sp.TNat,
                        ).layout(("to_", ("token_id", "amount")))
                    )
                ).layout(("from_", "txs"))
            ),
            self.data.tokenContractAddress,
            "transfer"
        ).open_some()

        arg = [
            sp.record(
                from_ = sp.self_address,
                txs = [
                    sp.record(
                        amount = params.value,
                        to_ = sp.sender,
                        token_id = self.data.tokenID
                    )
                ]
            )
        ]
        sp.transfer(arg, sp.mutez(0), handle)

        sp.verify(self.data.balances[sp.sender] >= params.value, Errors.ERROR_LOW_BALANCE)

        self.addAddressIfNecessary(sp.sender)
        self.data.balances[sp.sender] = sp.as_nat(self.data.balances[sp.sender] - params.value)

        
        # CHANGED
        # Write a checkpoint for the receiver
        self.writeCheckpoint(
            sp.record(
                checkpointedAddress = sp.sender,
                numCheckpoints = self.data.numCheckpoints.get(sp.sender, 0),
                newBalance = self.data.balances[sp.sender]
            )
        )


class Viewer(sp.Contract):
    def __init__(self, t):
        self.init(last = sp.none)
        self.init_type(sp.TRecord(last = sp.TOption(t)))
    @sp.entry_point
    def target(self, params):
        self.data.last = sp.some(params)

# Only run tests if this file is main.
if __name__ == "__main__":

    Addresses = sp.io.import_script_from_url("file:./test-helpers/addresses.py")

    ################################################################
    # getPriorBalance
    #
    # These tests are largely based off of Compound's tests:
    # https://github.com/compound-finance/compound-protocol/blob/master/tests/Governance/CompTest.js
    ################################################################

    @sp.add_test(name="getPriorBalance - reverts if block is not yet finalized")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)

        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # AND an alice has 100 tokens
        scenario += escrow.escrow(
            sp.record(
                value = 100,
            )
        ).run(
            level = sp.nat(0),
            sender = alice.address,
        )

        # WHEN a balance is requested for Alice for the current block
        # THEN the call fails
        level = sp.nat(1)
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = level
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
            valid = False
        )    

    @sp.add_test(name="getPriorBalance - returns 0 if there are no checkpoints")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)


        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # WHEN a balance is requested for Alice, who has no checkpoints
        requestLevel = 2
        currentLevel = sp.nat(14)
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = requestLevel
                ),
                viewer.typed.target
            )
        ).run(
            level = currentLevel
        )         

        # THEN the correct data is returned.
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == requestLevel)
        scenario.verify(viewer.data.last.open_some().result == sp.nat(0))

    @sp.add_test(name="getPriorBalance - returns 0 requested block is before the first checkpoint")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)

        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # AND an alice has 100 tokens in escrow
        firstCheckpointLevel = sp.nat(5)
        scenario += escrow.escrow(
            sp.record(
                value = 100,
            )
        ).run(
            level = firstCheckpointLevel,
            sender = alice.address,
        )


        # WHEN a balance is requested for Alice before her first checkpiont
        requestLevel = sp.as_nat(firstCheckpointLevel - 2)
        currentLevel = firstCheckpointLevel + 2
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = requestLevel
                ),
                viewer.typed.target
            )
        ).run(
            level = currentLevel
        )    

        # THEN the correct data is returned.
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == requestLevel)
        scenario.verify(viewer.data.last.open_some().result == sp.nat(0))

    @sp.add_test(name="getPriorBalance - returns last balance if requested block is after the lasts checkpoint")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)

        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # AND an alice has 100 tokens
        firstCheckpointLevel = sp.nat(5)
        amountEscrow = 100
        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            level = firstCheckpointLevel,
            sender = alice.address,
        )


        # WHEN a balance is requested for Alice before her first checkpiont
        requestLevel = firstCheckpointLevel + 2
        currentLevel = firstCheckpointLevel + 4
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = requestLevel
                ),
                viewer.typed.target
            )
        ).run(
            level = currentLevel
        )    


        # THEN the correct data is returned.
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == requestLevel)
        scenario.verify(viewer.data.last.open_some().result == amountEscrow)

    # Test searches across a few different checkpoints.
    # Test title in homage to:
    # https://github.com/compound-finance/compound-protocol/blob/9bcff34a5c9c76d51e51bcb0ca1139588362ef96/tests/Governance/CompTest.js#L157
    @sp.add_test(name="getPriorBalance - generally returns the balance at the appropriate checkpoint - even number of checkpoints")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)

        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # AND an alice has 100 tokens
        firstCheckpointLevel = sp.nat(0)
        amountEscrow = 100
        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            level = firstCheckpointLevel,
            sender = alice.address,
        )

        # And alice transfers Bob 10 tokens at a number of checkpoints such that the list is:
        # +-------+---------+
        # | block | balance |
        # +-------+---------+
        # | 2     | 200     |
        # +-------+---------+
        # | 4     | 300     |
        # +-------+---------+
        # | 6     | 400     |
        # +-------+---------+
        # | 8     | 300     |
        # +-------+---------+
        # | 10    | 400     |
        # +-------+---------+
        # | 12    | 0       |
        # +-------+---------+

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 2
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 4
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 6
        )     

        scenario += escrow.release(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 8
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 10
        )     

        scenario += escrow.release(
            sp.record(
                value = amountEscrow * 4,
            )
        ).run(
            sender = alice.address,
            level = 12
        )        

        # WHEN balances are requested for each checkpoint
        # THEN the correct answer is returned.

        # Sanity check - there are 5 checkpoints for Bob.
        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) > sp.nat(6))

        # level = 1
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = sp.nat(1)
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 1)
        scenario.verify(viewer.data.last.open_some().result == 100)


        # level = 2
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 2
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 2)
        scenario.verify(viewer.data.last.open_some().result == 200)

        # level = 3
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 3
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 3)
        scenario.verify(viewer.data.last.open_some().result == 200)

        # level = 4
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 4
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 4)
        scenario.verify(viewer.data.last.open_some().result == 300)

        # level = 5
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 5
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 5)
        scenario.verify(viewer.data.last.open_some().result == 300)    

        # level = 6
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 6
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 6)
        scenario.verify(viewer.data.last.open_some().result == 400)    

        # level = 7
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 7
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 7)
        scenario.verify(viewer.data.last.open_some().result == 400)   

        # level = 8
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 8
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 8)
        scenario.verify(viewer.data.last.open_some().result == 300)    

        # level = 9
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 9
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 9)
        scenario.verify(viewer.data.last.open_some().result == 300)     

        # level = 10
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 10
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 10)
        scenario.verify(viewer.data.last.open_some().result == 400)        

        # level = 11
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 11
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 11)
        scenario.verify(viewer.data.last.open_some().result == 400)    

        # level = 12
        level = 14
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 12
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 12)
        scenario.verify(viewer.data.last.open_some().result == 0)   

    # Test searches across a few different checkpoints.
    # Test title in homage to:
    # https://github.com/compound-finance/compound-protocol/blob/9bcff34a5c9c76d51e51bcb0ca1139588362ef96/tests/Governance/CompTest.js#L157
    @sp.add_test(name="getPriorBalance - generally returns the balance at the appropriate checkpoint - odd number of checkpoints")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)

        # AND a viewer contract.
        viewer = Viewer(
            t = sp.TRecord(result = sp.TNat, address = sp.TAddress, level = sp.TNat)
        )
        scenario += viewer

        # AND an alice has 100 tokens
        firstCheckpointLevel = sp.nat(0)
        amountEscrow = 100
        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            level = firstCheckpointLevel,
            sender = alice.address,
        )

        # And alice transfers Bob 10 tokens at a number of checkpoints such that the list is:
        # +-------+---------+
        # | block | balance |
        # +-------+---------+
        # | 2     | 200     |
        # +-------+---------+
        # | 4     | 300     |
        # +-------+---------+
        # | 6     | 400     |
        # +-------+---------+
        # | 8     | 300     |
        # +-------+---------+
        # | 10    | 400     |
        # +-------+---------+

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 2
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 4
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 6
        )     

        scenario += escrow.release(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 8
        )

        scenario += escrow.escrow(
            sp.record(
                value = amountEscrow,
            )
        ).run(
            sender = alice.address,
            level = 10
        )

        # WHEN balances are requested for each checkpoint
        # THEN the correct answer is returned.

        # Sanity check - there are 5 checkpoints for Bob.
        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) > sp.nat(5))

        # level = 1
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = sp.nat(1)
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 1)
        scenario.verify(viewer.data.last.open_some().result == 100)


        # level = 2
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 2
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 2)
        scenario.verify(viewer.data.last.open_some().result == 200)

        # level = 3
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 3
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 3)
        scenario.verify(viewer.data.last.open_some().result == 200)

        # level = 4
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 4
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 4)
        scenario.verify(viewer.data.last.open_some().result == 300)

        # level = 5
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 5
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 5)
        scenario.verify(viewer.data.last.open_some().result == 300)    

        # level = 6
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 6
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 6)
        scenario.verify(viewer.data.last.open_some().result == 400)    

        # level = 7
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 7
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 7)
        scenario.verify(viewer.data.last.open_some().result == 400)   

        # level = 8
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 8
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 8)
        scenario.verify(viewer.data.last.open_some().result == 300)    

        # level = 9
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 9
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 9)
        scenario.verify(viewer.data.last.open_some().result == 300)     

        # level = 10
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 10
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 10)
        scenario.verify(viewer.data.last.open_some().result == 400)        

        # level = 11
        level = 12
        scenario += escrow.getPriorBalance(
            (
                sp.record(
                    address = alice.address,
                    level = 11
                ),
                viewer.typed.target
            )
        ).run(
            level = level,
        )      
        scenario.verify(viewer.data.last.open_some().address == alice.address)
        scenario.verify(viewer.data.last.open_some().level == 11)
        scenario.verify(viewer.data.last.open_some().result == 400)              

    ################################################################
    # transfers
    #
    # Core transfer functionality tests are deferred to the token contract
    # tests by SmartPy. 
    #
    # These tests specifically test the checkpoint functionality, and are largely
    # based off of Compound's tests:
    # https://github.com/compound-finance/compound-protocol/blob/master/tests/Governance/CompTest.js
    ################################################################

    @sp.add_test(name="transfers - counts checkpoints correctly on transfers from owners")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")
        chorly   = sp.test_account("Chortle")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob, chorly])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice, Bob, Chorli.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)
        
        scenario += test_sdao.transfer(
        [
            test_sdao.batch_transfer.item(from_ = alice.address,
            txs = [
              sp.record(to_ = bob.address,
                        amount = 10000,
                        token_id = 0)
            ])
        ]).run(sender = alice)
        
        scenario += test_sdao.transfer(
        [
            test_sdao.batch_transfer.item(from_ = alice.address,
            txs = [
              sp.record(to_ = chorly.address,
                        amount = 10000,
                        token_id = 0)
            ])
        ]).run(sender = alice)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = bob.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = bob)
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = chorly.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = chorly)

        # AND an alice has 100 tokens
        scenario += escrow.escrow(
            sp.record(
                value = 100,
            )
        ).run(
            level = sp.nat(0),
            sender = alice.address
        )

        # WHEN a series of transfers are made
        # THEN token checkpoints are incremented properly

        # Alice releases 10.
        scenario += escrow.release(
            sp.record(
                value = 10,
            )
        ).run(
            level = sp.nat(1),
            sender = alice.address
        )

        # Bob escrows 10.
        scenario += escrow.escrow(
            sp.record(
                value = 10,
            )
        ).run(
            level = sp.nat(1),
            sender = bob.address
        )

        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) == sp.nat(2))
        scenario.verify(escrow.data.numCheckpoints.get(bob.address, sp.nat(0)) == sp.nat(1))
        scenario.verify(escrow.data.numCheckpoints.get(chorly.address, sp.nat(0)) == sp.nat(0))

        # Alice releases 10.
        scenario += escrow.release(
            sp.record(
                value = 10,
            )
        ).run(
            level = sp.nat(2),
            sender = alice.address
        )

        # Charlie escrows 10.
        scenario += escrow.escrow(
            sp.record(
                value = 10,
            )
        ).run(
            level = sp.nat(2),
            sender = chorly.address
        )

        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) == sp.nat(3))
        scenario.verify(escrow.data.numCheckpoints.get(bob.address, sp.nat(0)) == sp.nat(1))
        scenario.verify(escrow.data.numCheckpoints.get(chorly.address, sp.nat(0)) == sp.nat(1))

        # Bob releases 5.
        scenario += escrow.release(
            sp.record(
                value = 5,
            )
        ).run(
            level = sp.nat(3),
            sender = bob.address
        )

        # Charlie escrows 5.
        scenario += escrow.escrow(
            sp.record(
                value = 5,
            )
        ).run(
            level = sp.nat(3),
            sender = chorly.address
        )

        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) == sp.nat(3))
        scenario.verify(escrow.data.numCheckpoints.get(bob.address, sp.nat(0)) == sp.nat(2))
        scenario.verify(escrow.data.numCheckpoints.get(chorly.address, sp.nat(0)) == sp.nat(2))

        # AND history is recorded correctly for Alice.
        scenario.verify(escrow.data.checkpoints[(alice.address, 0)].fromBlock == 0)
        scenario.verify(escrow.data.checkpoints[(alice.address, 0)].balance == 100)

        scenario.verify(escrow.data.checkpoints[(alice.address, 1)].fromBlock == 1)
        scenario.verify(escrow.data.checkpoints[(alice.address, 1)].balance == 90)

        scenario.verify(escrow.data.checkpoints[(alice.address, 2)].fromBlock == 2)
        scenario.verify(escrow.data.checkpoints[(alice.address, 2)].balance == 80)

        # AND history is recorded correctly for Bob.
        scenario.verify(escrow.data.checkpoints[(bob.address, 0)].fromBlock == 1)
        scenario.verify(escrow.data.checkpoints[(bob.address, 0)].balance == 10)

        scenario.verify(escrow.data.checkpoints[(bob.address, 1)].fromBlock == 3)
        scenario.verify(escrow.data.checkpoints[(bob.address, 1)].balance == 5)

        # AND history is recorded correctly for Charlie.
        scenario.verify(escrow.data.checkpoints[(chorly.address, 0)].fromBlock == 2)
        scenario.verify(escrow.data.checkpoints[(chorly.address, 0)].balance == 10)

        scenario.verify(escrow.data.checkpoints[(chorly.address, 1)].fromBlock == 3)
        scenario.verify(escrow.data.checkpoints[(chorly.address, 1)].balance == 15)

    @sp.add_test(name="transfer - does not write two checkpoints for one block")
    def test():
        # GIVEN a Token contract
        scenario = sp.test_scenario()

        scenario.h1("FA2 Contract Deploying")
        scenario.table_of_contents()

        # sp.test_account generates ED25519 key-pairs deterministically:
        admin = sp.test_account("Administrator")
        alice = sp.test_account("Alice")
        bob   = sp.test_account("Robert")
        chorly   = sp.test_account("Chortle")

        # Let's display the accounts:
        scenario.h2("Accounts")
        scenario.show([admin, alice, bob, chorly])
        test_sdao = FA2_test.FA2(config = FA2_test.FA2_config(single_asset = True),
              metadata = sp.utils.metadata_of_url("https://example.com"),
              admin = admin.address)
        scenario += test_sdao

        scenario.h2("Initial Minting")

        scenario.p("The administrator mints 100 token-0's to Alice, Bob, Chorli.")

        tok0_md = FA2_test.FA2.make_metadata(
          name = "test sdao",
          decimals = 0,
          symbol= "TK0" )

        scenario += test_sdao.mint(address = alice.address,
                          amount = 690000,
                          metadata = tok0_md,
                          token_id = 0).run(sender = admin)
        
        scenario += test_sdao.transfer(
        [
            test_sdao.batch_transfer.item(from_ = alice.address,
            txs = [
              sp.record(to_ = bob.address,
                        amount = 10000,
                        token_id = 0)
            ])
        ]).run(sender = alice)
        
        scenario += test_sdao.transfer(
        [
            test_sdao.batch_transfer.item(from_ = alice.address,
            txs = [
              sp.record(to_ = chorly.address,
                        amount = 10000,
                        token_id = 0)
            ])
        ]).run(sender = alice)

        escrow = EscrowSDAO(
            tokenContractAddress = test_sdao.address,
            tokenID = sp.nat(0),
        )
        scenario += escrow

        scenario.p("Update Operators to escrow.")
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = alice.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = alice)
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = bob.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = bob)
        scenario += test_sdao.update_operators([
            sp.variant("add_operator", test_sdao.operator_param.make(
                owner = chorly.address,
                operator = escrow.address,
                token_id = 0)),
        ]).run(sender = chorly)

        # AND an alice has 100 tokens
        totalTokens = 100
        scenario += escrow.escrow(
            sp.record(
                value = totalTokens,
            )
        ).run(
            level = sp.nat(0),
            sender = alice.address
        )

        # WHEN two transfers to Bob are made in the same block.
        transferValue = sp.nat(10)
        level = sp.nat(1)
        
        # Alice releases.
        scenario += escrow.release(
            sp.record(
                value = transferValue,
            )
        ).run(
            level = level,
            sender = alice.address
        )

        # Bob escrows.
        scenario += escrow.escrow(
            sp.record(
                value = transferValue,
            )
        ).run(
            level = level,
            sender = bob.address
        )
        
        # Alice releases.
        scenario += escrow.release(
            sp.record(
                value = transferValue,
            )
        ).run(
            level = level,
            sender = alice.address
        )

        # Bob escrows.
        scenario += escrow.escrow(
            sp.record(
                value = transferValue,
            )
        ).run(
            level = level,
            sender = bob.address
        )

        # THEN Alice only records the transfer for the block once.
        scenario.verify(escrow.data.numCheckpoints.get(alice.address, sp.nat(0)) == sp.nat(2))
        scenario.verify(escrow.data.checkpoints[(alice.address, 0)].fromBlock == 0)
        scenario.verify(escrow.data.checkpoints[(alice.address, 0)].balance == totalTokens)

        scenario.verify(escrow.data.checkpoints[(alice.address, 1)].fromBlock == level)
        scenario.verify(escrow.data.checkpoints[(alice.address, 1)].balance == sp.as_nat(totalTokens - (transferValue * 2)))

        # AND Bob only records one checkpoint        
        scenario.verify(escrow.data.numCheckpoints.get(bob.address, sp.nat(0)) == sp.nat(1))
        scenario.verify(escrow.data.checkpoints[(bob.address, 0)].fromBlock == level)
        scenario.verify(escrow.data.checkpoints[(bob.address, 0)].balance == (transferValue * 2))

    sp.add_compilation_target("escrow", EscrowSDAO())
