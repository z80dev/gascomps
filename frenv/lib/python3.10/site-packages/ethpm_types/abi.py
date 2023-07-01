from typing import TYPE_CHECKING, List, Literal, Optional, Union

from pydantic import Extra, Field

from .base import BaseModel

if TYPE_CHECKING:
    from ethpm_types.contract_type import ContractType


class ABIType(BaseModel):
    name: Optional[str] = None
    """
    The name attached to the type, such as the input name of
    a function.
    """

    type: Union[str, "ABIType"]
    """
    The value-type, such as ``address`` or ``address[]``.
    """

    components: Optional[List["ABIType"]] = None
    """
    A field of sub-types that makes up this type.
    Tuples and structs tend to have this field.
    """

    internalType: Optional[str] = None
    """
    Another name for the type. Sometimes, compilers are able to populate
    this field with the struct or enum name.
    """

    class Config:
        extra = Extra.allow
        allow_mutation = False

    @property
    def canonical_type(self) -> str:
        """
        The low-level type recognized by the virtual machine.
        For example, a tuple is converted to comma-separated string
        of its components.
        """

        if "tuple" in self.type and self.components:  # NOTE: 2nd condition just to satisfy mypy
            value = f"({','.join(m.canonical_type for m in self.components)})"
            if "[" in self.type:
                value += f"[{str(self.type).split('[')[-1]}"

            return value

        elif isinstance(self.type, str):
            return self.type

        else:
            # Recursively discover the canonical type
            return self.type.canonical_type

    @property
    def signature(self) -> str:
        """
        If the type has name, returns ``"<canonical_type> <name>"``.
        Else, returns ``"<canonical_type>"``.
        """

        if self.name:
            return f"{self.canonical_type} {self.name}"
        else:
            return self.canonical_type


class EventABIType(ABIType):
    """
    ABI types describing event ABIs defined in contracts.
    """

    indexed: bool = False
    """
    Whether you can search logs based on this ABI type.
    **NOTE**: Only event ABI types should have this field
    """

    @property
    def signature(self) -> str:
        """
        The event signature.
        Will include the canonical type as well as the
        the name if it has one. Also notes indexed types.
        """

        sig = self.canonical_type
        # For events (handles both None and False conditions)
        if self.indexed:
            sig += " indexed"
        if self.name:
            sig += f" {self.name}"
        return sig


class ConstructorABI(BaseModel):
    """
    An ABI describing a contract constructor.
    **NOTE**: The constructor ABI does not have a ``name`` property.
    """

    type: Literal["constructor"]
    """The value ``"constructor"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    inputs: List[ABIType] = []
    """
    Contract constructor arguments.
    """

    @property
    def is_payable(self) -> bool:
        """
        Returns ``True`` if the contract accepts currency upon deployment.
        """

        return self.stateMutability == "payable"

    @property
    def signature(self) -> str:
        """
        String representing the function signature, which includes the arg names and types,
        for display purposes only.
        """

        input_args = ", ".join(i.signature for i in self.inputs)
        return f"constructor({input_args})"

    @property
    def selector(self) -> str:
        """
        String representing the constructor selector.
        """

        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"constructor({input_names})"


class FallbackABI(BaseModel):
    """
    An ABI dedicated to receiving unknown method selectors.
    **NOTE**: The fallback ABI does not have a name property.
    """

    type: Literal["fallback"]
    """The value ``"fallback"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    @property
    def is_payable(self) -> bool:
        """
        Returns ``True`` if the fallback accepts currency.
        """

        return self.stateMutability == "payable"

    @property
    def signature(self) -> str:
        """
        String representing the function signature for display purposes only.
        """
        return "fallback()"


class ReceiveABI(BaseModel):
    """
    An ABI dedicated to receiving currency from transactions with unknown
    method selectors.
    **NOTE**: The receive ABI does not have name field.
    """

    type: Literal["receive"]
    """The value ``"receive"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    stateMutability: Literal["payable"]
    """The value ``"payable"``."""

    @property
    def is_payable(self) -> bool:
        """
        Always returns ``True`` as receive methods are intended
        to receive money.
        """

        return True

    @property
    def signature(self) -> str:
        """
        String representing the function signature for display purposes only.
        """
        return "receive()"


class MethodABI(BaseModel):
    """
    An ABI representing a method you can invoke from a contact.
    """

    type: Literal["function"]
    """The value ``"function"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    name: str
    """The name of the method."""

    stateMutability: str = "nonpayable"
    """
    Can be either ``"payable"`` or ``"nonpayable"``.
    Defaults to the value ``"nonpayable"``.
    """

    inputs: List[ABIType] = []
    """
    Inputs to the method as :class:`~ethpm_types.abi.ABIType` objects.
    """

    outputs: List[ABIType] = []
    """
    What the method returns as :class:`~ethpm_types.abi.ABIType` objects.
    """

    @property
    def is_payable(self) -> bool:
        """
        Whether the method expects currency or not.
        """

        return self.stateMutability == "payable"

    @property
    def is_stateful(self) -> bool:
        """
        Whether the method alters the state of the blockchain
        (and likely requires a transaction).
        """

        return self.stateMutability not in ("view", "pure")

    @property
    def selector(self) -> str:
        """
        String representing the function selector, used to compute ``method_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the function signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        output_args = ""

        if self.outputs:
            output_args = " -> "
            if len(self.outputs) > 1:
                output_args += "(" + ", ".join(o.canonical_type for o in self.outputs) + ")"

            else:
                output_args += self.outputs[0].canonical_type

        return f"{self.name}({input_args}){output_args}"


class EventABI(BaseModel):
    """
    An ABI describing an event-type defined in a contract.
    """

    type: Literal["event"]
    """The value ``"event"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    name: str
    """The name of the event."""

    inputs: List[EventABIType] = []
    """
    Event properties defined as :class:`~ethpm_types.abi.EventABIType` objects.
    """

    anonymous: bool = False
    """``True`` if the event has no name."""

    @property
    def selector(self) -> str:
        """
        String representing the event selector, used to compute ``event_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the event signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        return f"{self.name}({input_args})"


class ErrorABI(BaseModel):
    """
    An ABI describing an error-type defined in a contract.
    """

    type: Literal["error"]
    """The value ``"error"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    name: str
    """The name of the error."""

    inputs: List[ABIType] = []
    """
    Inputs when raising the error defined as
    :class:`~ethpm_types.abi.ABIType` objects.
    """

    @property
    def selector(self) -> str:
        """
        String representing the event selector, used to compute ``event_id``.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.inputs)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the event signature, which includes the arg names and types,
        and output names and type(s) (if any) for display purposes only.
        """
        input_args = ", ".join(i.signature for i in self.inputs)
        return f"{self.name}({input_args})"


class StructABI(BaseModel):
    """
    An ABI describing a struct-type defined in a contract.
    """

    type: Literal["struct"]
    """The value ``"struct"``."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    name: str
    """The name of the struct."""

    members: List[ABIType]
    """The properties that compose the struct."""

    class Config:
        extra = Extra.allow

    @property
    def selector(self) -> str:
        """
        String representing the struct selector.
        """
        # NOTE: There is no space between input args for selector
        input_names = ",".join(i.canonical_type for i in self.members)
        return f"{self.name}({input_names})"

    @property
    def signature(self) -> str:
        """
        String representing the struct signature, which includes the member names and types,
        and offsets (if any) for display purposes only.
        """
        members_str = ", ".join(m.signature for m in self.members)
        return f"{self.name}({members_str})"


class UnprocessedABI(BaseModel):
    """
    An ABI representing an unknown entity.
    This is useful for supporting custom compiler types,
    such as types defined in L2 ecosystems but are not
    in Ethereum.
    """

    type: str
    """The type name as a string."""

    contract_type: Optional["ContractType"] = Field(None, exclude=True, repr=False)
    """
    A reference to this ABI's contract type. This gets set during ``ContractType``
    deserialization.
    """

    class Config:
        extra = Extra.allow

    @property
    def signature(self) -> str:
        """
        The full ABI JSON output, as we are unable to know
        a more useful-looking signature.
        """

        return self.json()


ABI = Union[
    ConstructorABI,
    FallbackABI,
    ReceiveABI,
    MethodABI,
    EventABI,
    ErrorABI,
    StructABI,
    UnprocessedABI,
]
