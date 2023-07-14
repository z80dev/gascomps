# @version ^0.3.9

from vyper.interfaces import ERC20

implements: ERC20

event Transfer:
    _from: indexed(address)
    _to: indexed(address)
    _value: uint256

event Approval:
    _owner: indexed(address)
    _spender: indexed(address)
    _value: uint256

name: public(immutable(String[10]))
symbol: public(immutable(String[3]))
decimals: public(constant(uint256)) = 18
totalSupply: public(uint256)

balanceOf: public(HashMap[address, uint256])
allowance: public(HashMap[address, HashMap[address, uint256]])

@external
def __init__():
    name = "Vypercoin"
    symbol = "VYC"
    self._mint(msg.sender, 1000000000000000000000000000)

@external
def approve(spender: address, amount: uint256) -> bool:
    self.allowance[msg.sender][spender] = amount
    log Approval(msg.sender, spender, amount)
    return True

@external
def increaseAllowance(spender: address, addedValue: uint256) -> bool:
    self.allowance[msg.sender][spender] += addedValue
    log Approval(msg.sender, spender, self.allowance[msg.sender][spender])
    return True

@external
def decreaseAllowance(spender: address, subtractedValue: uint256) -> bool:
    self.allowance[msg.sender][spender] -= subtractedValue
    log Approval(msg.sender, spender, self.allowance[msg.sender][spender])
    return True

@external
def transfer(_to: address, _value: uint256) -> bool:
    self.balanceOf[msg.sender] -= _value
    self.balanceOf[_to] += _value
    log Transfer(msg.sender, _to, _value)
    return True

@external
def transferFrom(_from: address, _to: address, _value: uint256) -> bool:
    self.allowance[_from][msg.sender] -= _value
    self.balanceOf[_from] -= _value
    self.balanceOf[_to] += _value
    log Transfer(_from, _to, _value)
    return True

################################################################
#                           EIP-2612                           #
################################################################

nonces: public(HashMap[address, uint256])

_DOMAIN_TYPEHASH: constant(bytes32) = keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)")
_PERMIT_TYPE_HASH: constant(bytes32) = keccak256("Permit(address owner,address spender,uint256 value,uint256 nonce,uint256 deadline)")


@external
def permit(owner: address, spender: address, amount: uint256, deadline: uint256, v: uint8, r: bytes32, s: bytes32):
    assert deadline >= block.timestamp
    nonce: uint256 = self.nonces[owner]
    self.nonces[owner] = nonce + 1

    domain_separator: bytes32 = keccak256(
        _abi_encode(_DOMAIN_TYPEHASH, name, "1.0", chain.id, self)
    )

    struct_hash: bytes32 = keccak256(_abi_encode(_PERMIT_TYPE_HASH, owner, spender, amount, nonce, deadline))
    hash: bytes32 = keccak256(
        concat(
            b"\x19\x01",
            domain_separator,
            struct_hash
        )
    )

    assert owner == ecrecover(hash, v, r, s)
    self.nonces[owner] += 1
    self.allowance[owner][spender] = amount
    log Approval(owner, spender, amount)

@internal
def _mint(_to: address, _value: uint256):
    self.balanceOf[_to] += _value
    self.totalSupply += _value
    log Transfer(ZERO_ADDRESS, _to, _value)

@internal
def _burn(_from: address, _value: uint256):
    assert self.balanceOf[_from] >= _value
    self.balanceOf[_from] -= _value
    self.totalSupply -= _value
    log Transfer(_from, ZERO_ADDRESS, _value)
