from functools import singledispatchmethod
from typing import Callable, Dict, Iterable, List, Optional, Type, TypeVar, Union

from eth_utils import add_0x_prefix, is_0x_prefixed
from pydantic import Field, validator

from ethpm_types.abi import (
    ABI,
    ConstructorABI,
    ErrorABI,
    EventABI,
    FallbackABI,
    MethodABI,
    ReceiveABI,
    StructABI,
)
from ethpm_types.ast import ASTNode
from ethpm_types.base import BaseModel
from ethpm_types.sourcemap import PCMap, SourceMap
from ethpm_types.utils import Hex, HexBytes, is_valid_hex

ABILIST_T = TypeVar("ABILIST_T", bound=Union[MethodABI, EventABI, StructABI, ErrorABI])
"""The generic used for the ABIList class. Only for type-checking."""

ABI_SINGLETON_T = TypeVar("ABI_SINGLETON_T", bound=Union[FallbackABI, ConstructorABI, ReceiveABI])
"""
The generic used for discovering the unique ABIs from the list.
Only for type-checking.
"""


# TODO link references & link values are for solidity, not used with Vyper
# Offsets are for dynamic links, e.g. EIP1167 proxy forwarder
class LinkDependency(BaseModel):
    offsets: List[int]
    """
    The locations within the corresponding bytecode where the value for this
    link value was written. These locations are 0-indexed from the beginning
    of the bytes representation of the corresponding bytecode.
    """

    type: str
    """
    The value type for determining what is encoded when linking the corresponding
    bytecode.
    """

    value: str
    """
    The value which should be written when linking the corresponding bytecode.
    """


class LinkReference(BaseModel):
    offsets: List[int]
    """
    An array of integers, corresponding to each of the start positions
    where the link reference appears in the bytecode. Locations are 0-indexed
    from the beginning of the bytes representation of the corresponding bytecode.
    This field is invalid if it references a position that is beyond the end of
    the bytecode.
    """

    length: int
    """
    The length in bytes of the link reference.
    This field is invalid if the end of the defined link reference exceeds the
    end of the bytecode.
    """

    name: Optional[str] = None
    """
    A valid identifier for the reference.
    Any link references which should be linked with the same link value should
    be given the same name.
    """


class Bytecode(BaseModel):
    bytecode: Optional[Hex] = None
    """
    A string containing the 0x prefixed hexadecimal representation of the bytecode.
    """

    linkReferences: Optional[List[LinkReference]] = None
    """
    The locations in the corresponding bytecode which require linking.
    """

    linkDependencies: Optional[List[LinkDependency]] = None
    """
    The link values that have been used to link the corresponding bytecode.
    """

    @validator("bytecode", pre=True)
    def prefix_bytecode(cls, v):
        if not v:
            return None
        return add_0x_prefix(v)

    def __repr__(self) -> str:
        self_str = super().__repr__()

        # Truncate bytecode for display
        if self.bytecode and len(self.bytecode) > 10:
            self_str = self_str.replace(
                self.bytecode, self.bytecode[:5] + "..." + self.bytecode[-3:]
            )

        return self_str

    def to_bytes(self) -> Optional[HexBytes]:
        if self.bytecode:
            return HexBytes(self.bytecode)

        # TODO: Resolve links to produce dynamically linked bytecode
        return None


class ContractInstance(BaseModel):
    contract_type: str = Field(..., alias="contractType")
    """
    Any of the contract type names included in this Package
    or any of the contract type names found in any of the package dependencies
    from the ``buildDependencies`` section of the Package Manifest.
    """

    address: Hex
    """The contract address."""

    transaction: Optional[Hex] = None
    """The transaction hash from which the contract was created."""

    block: Optional[Hex] = None
    """
    The block hash in which this the transaction which created this
    contract instance was mined.
    """

    runtime_bytecode: Optional[Bytecode] = Field(None, alias="runtimeBytecode")
    """
    The runtime portion of bytecode for this Contract Instance.
    When present, the value from this field supersedes the ``runtimeBytecode``
    from the :class:`~ethpm_types.contract_type.ContractType` for this
    ``ContractInstance``.
    """


class ABIList(List[ABILIST_T]):
    """
    Adds selection by name, selector and keccak(selector).
    """

    def __init__(
        self,
        iterable: Optional[Iterable[ABILIST_T]] = None,
        *,
        selector_id_size: int = 32,
        selector_hash_fn: Optional[Callable[[str], bytes]] = None,
    ):
        self._selector_id_size = selector_id_size
        self._selector_hash_fn = selector_hash_fn
        super().__init__(iterable or ())

    @singledispatchmethod
    def __getitem__(self, selector):
        raise NotImplementedError(f"Cannot use {type(selector)} as a selector.")

    @__getitem__.register
    def __getitem_int(self, selector: int):
        return super().__getitem__(selector)

    @__getitem__.register
    def __getitem_slice(self, selector: slice):
        return super().__getitem__(selector)

    @__getitem__.register
    def __getitem_str(self, selector: str):
        try:
            if "(" in selector:
                # String-style selector e.g. `method(arg0)`.
                return next(abi for abi in self if abi.selector == selector)

            elif is_0x_prefixed(selector):
                # Hashed bytes selector, but as a hex str.
                return self.__getitem__(HexBytes(selector))

            # Search by name (could be ambiguous()
            return next(abi for abi in self if abi.name == selector)

        except StopIteration:
            raise KeyError(selector)

    @__getitem__.register
    def __getitem_bytes(self, selector: bytes):
        try:
            if self._selector_hash_fn:
                return next(
                    abi
                    for abi in self
                    if self._selector_hash_fn(abi.selector)[: self._selector_id_size]
                    == selector[: self._selector_id_size]
                )

            else:
                raise KeyError(selector)

        except StopIteration:
            raise KeyError(selector)

    @__getitem__.register
    def __getitem_method_abi(self, selector: MethodABI):
        return self.__getitem__(selector.selector)

    @__getitem__.register
    def __getitem_event_abi(self, selector: EventABI):
        return self.__getitem__(selector.selector)

    @singledispatchmethod
    def __contains__(self, selector):
        raise NotImplementedError(f"Cannot use {type(selector)} as a selector.")

    @__contains__.register
    def __contains_str(self, selector: str) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_bytes(self, selector: bytes) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_method_abi(self, selector: MethodABI) -> bool:
        return self._contains(selector)

    @__contains__.register
    def __contains_event_abi(self, selector: EventABI) -> bool:
        return self._contains(selector)

    def _contains(self, selector: Union[str, bytes, MethodABI, EventABI]) -> bool:
        try:
            _ = self[selector]
            return True
        except (KeyError, IndexError):
            return False


class ContractType(BaseModel):
    """
    A serializable type representing the type of a contract.
    For example, if you define your contract as ``contract MyContract`` (in Solidity),
    then ``MyContract`` would be the type.
    """

    name: Optional[str] = Field(None, alias="contractName")
    """
    The name of the contract type. The field is optional if ``ContractAlias``
    is the same as ``ContractName``.
    """

    source_id: Optional[str] = Field(None, alias="sourceId")
    """
    The global source identifier for the source file from which this contract type was generated.
    """

    deployment_bytecode: Optional[Bytecode] = Field(None, alias="deploymentBytecode")
    """The bytecode for the ContractType."""

    runtime_bytecode: Optional[Bytecode] = Field(None, alias="runtimeBytecode")
    """The unlinked 0x-prefixed runtime portion of bytecode for this ContractType."""

    abi: List[ABI] = []
    """The application binary interface to the contract."""

    sourcemap: Optional[SourceMap] = None
    """
    The range of the source code that is represented by the respective node in the AST.
    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    pcmap: Optional[PCMap] = None
    """
    The program counter map representing which lines in the source code account for which
    instructions in the bytecode.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    dev_messages: Optional[Dict[int, str]] = None
    """
    A map of dev-message comments in the source contract by their starting line number.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    ast: Optional[ASTNode] = None
    """
    The contract's root abstract syntax tree node.

    **NOTE**: This is not part of the canonical EIP-2678 spec.
    """

    userdoc: Optional[dict] = None
    devdoc: Optional[dict] = None

    def __repr__(self) -> str:
        repr_id = self.__class__.__name__
        if self.name:
            repr_id = f"{repr_id} {self.name}"

        return f"<{repr_id}>"

    def get_runtime_bytecode(self) -> Optional[HexBytes]:
        if self.runtime_bytecode:
            return self.runtime_bytecode.to_bytes()

        return None

    def get_deployment_bytecode(self) -> Optional[HexBytes]:
        if self.deployment_bytecode:
            return self.deployment_bytecode.to_bytes()

        return None

    @property
    def constructor(self) -> ConstructorABI:
        """
        The constructor of the contract, if it has one. For example,
        your smart-contract (in Solidity) may define a ``constructor() public {}``.
        This property contains information about the parameters needed to initialize
        a contract.
        """

        # Use default constructor (no args) when no defined.
        abi = self._get_first_instance(ConstructorABI) or ConstructorABI(type="constructor")
        abi.contract_type = self
        return abi

    @property
    def fallback(self) -> Optional[FallbackABI]:
        """
        The fallback method of the contract, if it has one. A fallback method
        is external, has no name, arguments, or return value, and gets invoked
        when the user attempts to call a method that does not exist.
        """

        return self._get_first_instance(FallbackABI)

    @property
    def receive(self) -> Optional[ReceiveABI]:
        """
        The ``receive()`` method of the contract, if it has one. A contract may
        have 0-1 ``receive()`` methods defined. It gets executed when calling
        the contract with empty calldata. The method is not allowed any arguments
        and cannot return anything.
        """

        return self._get_first_instance(ReceiveABI)

    @property
    def view_methods(self) -> ABIList[MethodABI]:
        """
        The call-methods (read-only method, non-payable methods) defined in a smart contract.

        Returns:
            List[:class:`~ethpm_types.abi.ABI`]
        """
        return self._get_abis(
            selector_id_size=4, filter_fn=lambda x: isinstance(x, MethodABI) and not x.is_stateful
        )

    @property
    def mutable_methods(self) -> ABIList[MethodABI]:
        """
        The transaction-methods (stateful or payable methods) defined in a smart contract.

        Returns:
            List[:class:`~ethpm_types.abi.ABI`]
        """
        return self._get_abis(
            selector_id_size=4, filter_fn=lambda x: isinstance(x, MethodABI) and x.is_stateful
        )

    @property
    def events(self) -> ABIList[EventABI]:
        """
        The events defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(filter_fn=lambda a: isinstance(a, EventABI))

    @property
    def errors(self) -> ABIList[ErrorABI]:
        """
        The errors defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(selector_id_size=4, filter_fn=lambda a: isinstance(a, ErrorABI))

    @property
    def methods(self) -> ABIList:
        """
        All methods defined in a smart contract.

        Returns:
            :class:`~ethpm_types.contract_type.ABIList`
        """
        return self._get_abis(selector_id_size=4, filter_fn=lambda a: isinstance(a, MethodABI))

    def _selector_hash_fn(self, selector: str) -> bytes:
        # keccak is the default on most ecosystems, other ecosystems can subclass to override it
        from eth_utils import keccak

        return keccak(text=selector)

    def _get_abis(
        self,
        selector_id_size: int = 32,
        filter_fn: Optional[Callable[[ABI], bool]] = None,
    ):
        def noop(a: ABI) -> bool:
            return True

        filter_fn = filter_fn or noop
        method_abis = [abi for abi in self.abi if filter_fn(abi)]
        for abi in method_abis:
            abi.contract_type = self

        return ABIList(
            method_abis,
            selector_id_size=selector_id_size,
            selector_hash_fn=self._selector_hash_fn,
        )

    def _get_first_instance(self, _type: Type[ABI_SINGLETON_T]) -> Optional[ABI_SINGLETON_T]:
        for abi in self.abi:
            if not isinstance(abi, _type):
                continue

            # TODO: Figure out better way than type ignore.
            #  getting `<nothing> has no attribute contract_type`.
            #  probably using generics wrong but not sure how else to do it.
            abi.contract_type = self  # type: ignore[attr-defined]
            return abi

        return None


class BIP122_URI(str):
    """
    A URI scheme for looking up blocks.
    `BIP-122 <https://github.com/bitcoin/bips/blob/master/bip-0122.mediawiki>`__.

    URI Format::

        blockchain://<chain>/<block>/<hash>

    """

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            pattern="^blockchain://[0-9a-f]{64}/block/[0-9a-f]{64}$",
            examples=[
                "blockchain://d4e56740f876aef8c010b86a40d5f56745a118d0906a34e69aec8c0db1cb8fa3"
                "/block/752820c0ad7abc1200f9ad42c4adc6fbb4bd44b5bed4667990e64565102c1ba6",
            ],
        )

    @classmethod
    def __get_validators__(cls):
        yield cls.validate_uri
        yield cls.validate_genesis_hash
        yield cls.validate_block_hash

    @classmethod
    def validate_uri(cls, uri):
        if not uri.startswith("blockchain://"):
            raise ValueError("Must use 'blockchain' protocol.")

        if len(uri.replace("blockchain://", "").split("/")) != 3:
            raise ValueError("Must be referenced via <genesis_hash>/block/<block_hash>.")

        _, block_keyword, _ = uri.replace("blockchain://", "").split("/")
        if block_keyword != "block":
            raise ValueError("Must use block reference.")

        return uri

    @classmethod
    def validate_genesis_hash(cls, uri):
        genesis_hash, _, _ = uri.replace("blockchain://", "").split("/")
        if not is_valid_hex("0x" + genesis_hash):
            raise ValueError(f"Hash is not valid: {genesis_hash}.")

        if len(genesis_hash) != 64:
            raise ValueError(f"Hash is not valid length: {genesis_hash}.")

        return uri

    @classmethod
    def validate_block_hash(cls, uri):
        _, _, block_hash = uri.replace("blockchain://", "").split("/")
        if not is_valid_hex("0x" + block_hash):
            raise ValueError(f"Hash is not valid: {block_hash}.")

        if len(block_hash) != 64:
            raise ValueError(f"Hash is not valid length: {block_hash}.")

        return uri
