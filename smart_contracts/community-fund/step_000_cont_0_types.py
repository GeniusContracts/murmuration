import smartpy as sp

tstorage = sp.TRecord(governorAddress = sp.TAddress, metadata = sp.TBigMap(sp.TString, sp.TBytes)).layout(("governorAddress", "metadata"))
tparameter = sp.TVariant(default = sp.TUnit, rescueFA12 = sp.TRecord(amount = sp.TNat, destination = sp.TAddress, tokenContractAddress = sp.TAddress).layout(("tokenContractAddress", ("amount", "destination"))), rescueFA2 = sp.TRecord(amount = sp.TNat, destination = sp.TAddress, tokenContractAddress = sp.TAddress, tokenId = sp.TNat).layout(("tokenContractAddress", ("tokenId", ("amount", "destination")))), rescueXTZ = sp.TRecord(destinationAddress = sp.TAddress).layout("destinationAddress"), setDelegate = sp.TOption(sp.TKeyHash), setGovernorContract = sp.TAddress).layout((("default", ("rescueFA12", "rescueFA2")), ("rescueXTZ", ("setDelegate", "setGovernorContract"))))
tprivates = { }
tviews = { }
