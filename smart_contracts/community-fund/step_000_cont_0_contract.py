import smartpy as sp

class Contract(sp.Contract):
  def __init__(self):
    self.init_type(sp.TRecord(governorAddress = sp.TAddress, metadata = sp.TBigMap(sp.TString, sp.TBytes)).layout(("governorAddress", "metadata")))
    self.init(governorAddress = sp.address('tz1VmiY38m3y95HqQLjMwqnMS7sdMfGomzKi'),
              metadata = {'' : sp.bytes('0x74657a6f732d73746f726167653a64617461'), 'data' : sp.bytes('0x7b20226e616d65223a202253616c736144414f205472656173757279222c20226465736372697074696f6e223a2022546f6b656e205265706f7369746f727920666f722053616c736144414f222c2022617574686f7273223a205b2247656e69757320436f6e747261637473225d2c2022686f6d6570616765223a20202268747470733a2f2f73616c736164616f2e78797a22207d')})

  @sp.entry_point
  def default(self):
    pass

  @sp.entry_point
  def rescueFA12(self, params):
    sp.set_type(params, sp.TRecord(amount = sp.TNat, destination = sp.TAddress, tokenContractAddress = sp.TAddress).layout(("tokenContractAddress", ("amount", "destination"))))
    sp.verify(sp.sender == self.data.governorAddress, 'NOT_GOVERNOR')
    sp.transfer(sp.record(from_ = sp.self_address, to_ = params.destination, value = params.amount), sp.tez(0), sp.contract(sp.TRecord(from_ = sp.TAddress, to_ = sp.TAddress, value = sp.TNat).layout(("from_ as from", ("to_ as to", "value"))), params.tokenContractAddress, entry_point='transfer').open_some())

  @sp.entry_point
  def rescueFA2(self, params):
    sp.set_type(params, sp.TRecord(amount = sp.TNat, destination = sp.TAddress, tokenContractAddress = sp.TAddress, tokenId = sp.TNat).layout(("tokenContractAddress", ("tokenId", ("amount", "destination")))))
    sp.verify(sp.sender == self.data.governorAddress, 'NOT_GOVERNOR')
    sp.transfer(sp.list([sp.record(from_ = sp.self_address, txs = sp.list([sp.record(to_ = params.destination, token_id = params.tokenId, amount = params.amount)]))]), sp.tez(0), sp.contract(sp.TList(sp.TRecord(from_ = sp.TAddress, txs = sp.TList(sp.TRecord(amount = sp.TNat, to_ = sp.TAddress, token_id = sp.TNat).layout(("to_", ("token_id", "amount"))))).layout(("from_", "txs"))), params.tokenContractAddress, entry_point='transfer').open_some())

  @sp.entry_point
  def rescueXTZ(self, params):
    sp.set_type(params, sp.TRecord(destinationAddress = sp.TAddress).layout("destinationAddress"))
    sp.verify(sp.sender == self.data.governorAddress, 'NOT_GOVERNOR')
    sp.send(params.destinationAddress, sp.balance)

  @sp.entry_point
  def setDelegate(self, params):
    sp.set_type(params, sp.TOption(sp.TKeyHash))
    sp.verify(sp.sender == self.data.governorAddress, 'NOT_GOVERNOR')
    sp.set_delegate(params)

  @sp.entry_point
  def setGovernorContract(self, params):
    sp.set_type(params, sp.TAddress)
    sp.verify(sp.sender == self.data.governorAddress, 'NOT_GOVERNOR')
    self.data.governorAddress = params

sp.add_compilation_target("test", Contract())