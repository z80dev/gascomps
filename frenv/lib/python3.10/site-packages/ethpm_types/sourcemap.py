from typing import Dict, Iterator, List, Optional, Union

from pydantic import root_validator

from ethpm_types.base import BaseModel
from ethpm_types.utils import SourceLocation


class SourceMapItem(BaseModel):
    """
    An object modeling a node in a source map; useful for mapping
    the source map string back to source code.
    """

    # NOTE: `None` entry means this path was inserted by the compiler during codegen
    start: Optional[int]
    """
    The byte-offset start of the range in the source file.
    """

    length: Optional[int]
    """
    The byte-offset length.
    """

    contract_id: Optional[int]
    """
    The source identifier.
    """

    jump_code: str
    """
    An identifier for whether a jump goes into a function, returns from a function,
    or is part of a loop.
    """
    # NOTE: ignore "modifier_depth" keyword introduced in solidity >0.6.x

    @classmethod
    def parse_str(cls, src_str: str, previous: Optional["SourceMapItem"] = None) -> "SourceMapItem":
        row: List[Union[int, str]] = [int(i) if i.isnumeric() else i for i in src_str.split(":")]

        if previous is None:
            start = int(cls._extract_value(row, 0) or -1)
            length = int(cls._extract_value(row, 1) or -1)
            contract_id = int(cls._extract_value(row, 2) or -1)
            jump_code = cls._extract_value(row, 3) or ""

        else:
            start = int(cls._extract_value(row, 0, previous=previous.start or -1))
            length = int(cls._extract_value(row, 1, previous=previous.length or -1))
            contract_id = int(cls._extract_value(row, 2, previous=previous.contract_id or -1))
            jump_code = cls._extract_value(row, 3, previous=previous.jump_code or "")

        return SourceMapItem.construct(
            # NOTE: `-1` for these three entries means `None`
            start=start if start != -1 else None,
            length=length if length != -1 else None,
            contract_id=contract_id if contract_id != -1 else None,
            jump_code=jump_code,
        )

    @staticmethod
    def _extract_value(
        row: List[Union[str, int]], item_idx: int, previous: Optional[Union[int, str]] = None
    ):
        if len(row) > item_idx and row[item_idx] != "":
            return row[item_idx]

        return previous


class SourceMap(BaseModel):
    """
    As part of the Abstract Syntax Tree (AST) output, the compiler provides the range
    of the source code that is represented by the respective node in the AST.

    This can be used for various purposes ranging from static analysis tools that
    report errors based on the AST and debugging tools that highlight local variables
    and their uses.

    `Solidity Doc <https://docs.soliditylang.org/en/v0.8.15/internals/source_mappings.html>`__.
    """

    __root__: str

    def __repr__(self) -> str:
        return self.__root__

    def __str__(self) -> str:
        return self.__root__

    def parse(self) -> Iterator[SourceMapItem]:
        """
        Parses the source map string into a stream of
        :class:`~ethpm_types.contract_type.SourceMapItem` items.
        Useful for when parsing the map according to compiler-specific
        decompilation rules back to the source code language files.

        Returns:
            Iterator[:class:`~ethpm_types.contract_type.SourceMapItem`]
        """

        item = None

        # NOTE: Format of SourceMap is like `1:2:3:a;;4:5:6:b;;;`
        #       where an empty entry means to copy the previous step.
        #       This is because sourcemaps are compressed to save space.
        for i, row in enumerate(self.__root__.strip().split(";")):
            item = SourceMapItem.parse_str(row, previous=item)
            yield item


class PCMapItem(BaseModel):
    """
    Line information for a given EVM instruction.

    These are utilized in the pc-map by which the compiler generates source code spans for given
    program counter positions.
    """

    line_start: Optional[int] = None
    column_start: Optional[int] = None
    line_end: Optional[int] = None
    column_end: Optional[int] = None
    dev: Optional[str] = None

    @property
    def location(self) -> SourceLocation:
        return (
            (self.line_start or -1),
            (self.column_start or -1),
            (self.line_end or -1),
            (self.column_end or -1),
        )


_RawPCMapItem = Dict[str, Optional[Union[str, List[Optional[int]]]]]
_RawPCMap = Dict[str, _RawPCMapItem]


class PCMap(BaseModel):
    """
    A map of program counter values to statements in the source code.

    This can be used for various purposes ranging from static analysis tools that
    report errors based on the program counter value and debugging tools that highlight local
    variables and their uses.
    """

    __root__: _RawPCMap

    @root_validator(pre=True)
    def validate_full(cls, value):
        # * Allows list values; turns them to {"location": value}.
        # * Allows `None`; turns it to {"location": None}
        # Else, expects dictionaries. This allows starting with a simple
        # location data but allowing compilers to enrich fields.

        return {
            "__root__": {
                k: ({"location": v} if isinstance(v, list) else v or {"location": None})
                for k, v in ((value or {}).get("__root__", value) or {}).items()
            }
        }

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}>"

    def __getitem__(self, pc: Union[int, str]) -> _RawPCMapItem:
        return self.__root__[str(pc)]

    def __setitem__(self, pc: Union[int, str], value: _RawPCMapItem):
        if isinstance(value, list):
            value = {"location": value}

        self.__root__[str(pc)] = value

    def __contains__(self, pc: Union[int, str]) -> bool:
        return str(pc) in self.__root__

    def parse(self) -> Dict[int, PCMapItem]:
        """
        Parses the pc map string into a map of ``PCMapItem`` items, using integer pc values as keys.

        The format from the compiler will have numeric string keys with lists of ints for values.
        These integers represent (in order) the starting line, starting column, ending line, and
        ending column numbers.
        """
        results = {}

        for key, value in self.__root__.items():
            if value["location"] is not None:
                result = PCMapItem(
                    line_start=value["location"][0],
                    column_start=value["location"][1],
                    line_end=value["location"][2],
                    column_end=value["location"][3],
                    dev=value.get("dev"),
                )
            else:
                result = PCMapItem(dev=value.get("dev"))

            results[int(key)] = result

        return results
