from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set, Tuple, Union

import requests
from cid import make_cid  # type: ignore
from pydantic import root_validator, validator

from ethpm_types.ast import ASTClassification, ASTNode, SourceLocation
from ethpm_types.base import BaseModel
from ethpm_types.contract_type import ContractType
from ethpm_types.sourcemap import PCMap
from ethpm_types.utils import (
    CONTENT_ADDRESSED_SCHEMES,
    Algorithm,
    AnyUrl,
    Hex,
    HexBytes,
    compute_checksum,
)


class Compiler(BaseModel):
    name: str
    """Which compiler was used in compilation."""

    version: str
    """
    The version of the compiler.
    The field should be OS agnostic (OS not included in the string) and take
    the form of either the stable version in semver format or if built on a nightly
    should be denoted in the form of <semver>-<commit-hash> ex: 0.4.8-commit.60cc1668.
    """

    settings: Optional[dict] = None
    """
    Any settings or configuration that was used in compilation. For the ``solc`` compiler,
    this should conform to the
    [Compiler Input and Output Description](https://docs.soliditylang.org/en/latest/using-the-compiler.html#compiler-input-and-output-json-description).
    """  # noqa: E501

    contractTypes: Optional[List[str]] = None
    """
    A list of the contract type names in this package
    that used this compiler to generate its outputs.
    """


class Checksum(BaseModel):
    """Checksum information about the contents of a source file."""

    algorithm: Algorithm
    """
    The algorithm used to generate the corresponding hash.
    Possible algorithms include, but are not limited to sha3, sha256, md5, keccak256.
    """

    hash: Hex
    """
    The hash of a source files contents generated with the corresponding algorithm.
    """


class Content(BaseModel):
    """
    A wrapper around source code line numbers mapped to the content
    string of those lines.
    """

    __root__: Dict[int, str]

    @property
    def begin_lineno(self) -> int:
        return self.line_numbers[0] if self.line_numbers else -1

    @property
    def end_lineno(self) -> int:
        return self.line_numbers[-1] if self.line_numbers else -1

    @property
    def line_numbers(self) -> List[int]:
        """
        All line number in order for this piece of content.
        """
        return sorted(list(self.__root__.keys()))

    @root_validator(pre=True)
    def validate_dict(cls, value):
        data = value["__root__"] if "__root__" in value else value
        return {
            "__root__": (
                {i + 1: x for i, x in enumerate(data.splitlines())}
                if isinstance(data, str)
                else data
            )
        }

    def encode(self, *args, **kwargs) -> bytes:
        return str(self).encode(*args, **kwargs)

    def items(self):
        return self.__root__.items()

    def as_list(self) -> List[str]:
        return list(self.__root__.values())

    def __str__(self) -> str:
        res = "\n".join(self.__root__.values())
        if res and not res.endswith("\n"):
            res = f"{res}\n"

        return res

    def __getitem__(self, lineno: Union[int, slice]) -> Union[List[str], str]:
        if isinstance(lineno, int):
            return self.__root__[lineno]

        # Handle slice of linenos.
        numbers = self.line_numbers
        start = numbers[0] if lineno.start is None else lineno.start
        stop = numbers[-1] if lineno.stop is None else lineno.stop
        lines = []
        for no in numbers:
            if start <= no < stop:
                lines.append(self.__root__[no])
            elif no >= stop:
                break

        return lines

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        return iter(self.__root__.values())

    def __len__(self) -> int:
        return len(self.__root__)


class Source(BaseModel):
    """Information about a source file included in a Package Manifest."""

    urls: List[AnyUrl] = []
    """Array of urls that resolve to the same source file."""

    checksum: Optional[Checksum] = None
    """
    Hash of the source file. Per EIP-2678,
    this field is only necessary if source must be fetched.
    """

    content: Optional[Content] = None
    """Inlined contract source."""

    installPath: Optional[str] = None
    """
    Filesystem path of source file.
    **NOTE**: This was probably done for solidity, needs files cached to disk for compiling.
    If processing a local project, code already exists, so no issue.
    If processing remote project, cache them in ape project data folder
    """

    type: Optional[str] = None
    """The type of the source file."""

    license: Optional[str] = None
    """The type of license associated with this source file."""

    references: Optional[List[str]] = None
    """
    List of `Source` objects that depend on this object.
    **NOTE**: Not a part of canonical EIP-2678 spec.
    """
    # TODO: Add `SourceId` type and use instead of `str`

    imports: Optional[List[str]] = None
    """
    List of source objects that this object depends on.
    **NOTE**: Not a part of canonical EIP-2678 spec.
    """
    # TODO: Add `SourceId` type and use instead of `str`

    @root_validator(pre=True)
    def validate_model(cls, model):
        if isinstance(model.get("content"), str):
            model["content"] = Content(
                __root__={i + 1: x for i, x in enumerate(model["content"].splitlines())}
            )

        return model

    def __repr__(self) -> str:
        repr_id = "Source"

        if self.urls:
            # Favor URI when available.
            primary_uri = self.urls[0]
            repr_id = f"{repr_id} {primary_uri}"

        elif self.checksum:
            repr_id = f"{repr_id} {self.checksum.hash}"

        return f"<{repr_id}>"

    def __getitem__(self, index: Union[int, slice]):
        """
        Get a line or slice of lines from ``content``.

        Args:
            index (int, slice): The line index.
        """

        if self.content is None:
            raise IndexError("Source has no fetched content.")

        line_numbers = self.content.line_numbers
        lineno: Union[List[int], int] = line_numbers[index]
        return (
            [self.content[x] for x in lineno] if isinstance(lineno, list) else self.content[lineno]
        )

    def __iter__(self) -> Iterator[str]:  # type: ignore
        if self.content is None:
            raise ValueError("Source has no fetched content.")

        return iter(self.content.__root__.values())

    def __len__(self) -> int:
        if self.content is None:
            raise ValueError("Source has no fetched content.")

        return len(self.content)

    def dict(self, *args, **kwargs) -> dict:
        res = super().dict()
        if self.content is not None:
            res["content"] = str(self.content)
        elif "content" in res:
            del res["content"]

        return res

    def fetch_content(self) -> str:
        """
        Fetch the content for the given Source object.
        Loads resource at ``urls`` into ``content`` if not available.

        Returns:
            str
        """

        # NOTE: This is a trapdoor to bypass fetching logic if already available
        if self.content is not None:
            return str(self.content)

        if len(self.urls) == 0:
            raise ValueError("No content to fetch.")

        for url in map(str, self.urls):
            # TODO: Have more robust handling of IPFS URIs
            if url.startswith("ipfs"):
                url = url.replace("ipfs://", "https://ipfs.io/ipfs/")

            response = requests.get(url)
            if response.status_code == 200:
                return response.text

        raise ValueError("Could not fetch content.")

    def calculate_checksum(self, algorithm: Algorithm = Algorithm.MD5) -> Checksum:
        """
        Compute the checksum of the ``Source`` object.
        Will short-circuit to content identifier if using content-addressed file references
        Fails if ``content`` isn't available locally or by fetching.

        Args:
            algorithm (Optional[:class:`~ethpm_types.utils.Algorithm`]): The algorithm to use
              to compute the checksum with. Defaults to MD5.

        Returns:
            :class:`~ethpm_types.source.Checksum`
        """

        # NOTE: Content-addressed URI schemes have checksum encoded directly in address.
        for url in self.urls:
            if url.scheme in CONTENT_ADDRESSED_SCHEMES:
                # TODO: Pull algorithm for checksum calc from codec
                cid = make_cid(url.host)
                return Checksum(hash=cid.multihash.hex(), algorithm=Algorithm.SHA256)

        content = self.fetch_content()
        return Checksum(
            hash=compute_checksum(content.encode("utf8"), algorithm=algorithm),
            algorithm=algorithm,
        )

    def content_is_valid(self) -> bool:
        """
        Return if content is corrupted.
        Will never be corrupted if content is locally available.
        If content is referenced by content addressed identifier,
        will not be corrupted either.
        If referenced from a server URL,
        then checksum must be present and will be validated against.

        Returns:
            bool
        """

        # NOTE: Per EIP-2678, checksum is not needed if content does not need to be fetched
        if self.content is not None:
            return True

        # NOTE: Per EIP-2678, Checksum is not required if a URL is content addressed.
        #       This is because the act of fetching the content validates the checksum.
        for url in self.urls:
            if url.scheme in CONTENT_ADDRESSED_SCHEMES:
                return True

        if self.checksum:
            return self.checksum == self.calculate_checksum(algorithm=self.checksum.algorithm)

        return False


class Closure(BaseModel):
    """
    A wrapper around code ran, such as a function.
    """

    name: str
    """The name of the definition."""

    full_name: Optional[str] = None
    """This is a unique name of the definition."""


class Function(Closure):
    """
    Data about a function in a contract with known source code.
    """

    ast: ASTNode
    """The function definition AST node."""

    offset: int
    """The line number of the first AST after the signature."""

    content: Content
    """The function's line content after the signature, mapped by line numbers."""

    @validator("ast", pre=True)
    def validate_ast(cls, value):
        if (
            value.classification is not ASTClassification.FUNCTION
            and "function" not in str(value.ast_type).lower()
        ):
            raise ValueError(
                f"`ast` must be a function definition (classification={value.classification})."
            )

        return value

    def __str__(self) -> str:
        return self.name

    def __repr__(self) -> str:
        name = self.name[:30].rstrip()
        if len(name) < len(self.name):
            name = f"{name} ... "

        return f"<Function {name}>"

    def get_content(self, location: SourceLocation) -> Content:
        """
        Get the source content for the given location.

        Args:
            location (``SourceLocation``): The location of the content.

        Returns:
            ``ethpm_types.source.Content``
        """

        start = max(location[0], self.content.begin_lineno)
        stop = location[2] + 1
        content = {n: self.content[n] for n in range(start, stop) if n in self.content.line_numbers}
        return Content(__root__=content)

    def get_content_asts(self, location: SourceLocation) -> List[ASTNode]:
        """
        Get all AST nodes for the given location.

        Args:
            location (``SourceLocation``): The location of the content.

        Returns:
            ``List[ASTNode]``: AST nodes objects.
        """

        return [
            a
            for a in self.ast.get_nodes_at_line(location)
            if a.lineno >= location[0] and a.classification is not ASTClassification.FUNCTION
        ]


class Statement(BaseModel):
    """
    A class representing an item in a control flow, either a source statement
    or implicit compiler code.
    """

    type: str
    """
    The type of statement it is, such as `source` or a virtual identifier.
    """

    pcs: Set[int] = set()
    """
    The PC value for the statement.
    """

    def __repr__(self) -> str:
        return f"<Statement type={self.type}>"


class SourceStatement(Statement):
    """
    A class mapping an AST node to some source code content.
    """

    type: str = "source"

    asts: List[ASTNode]
    """The AST nodes from this statement."""

    content: Content
    """The source code content connected to the AST node."""

    def __len__(self):
        return len(self.content.as_list())

    def __getitem__(self, idx: int) -> str:
        return self.content.as_list()[idx]

    def __iter__(self) -> Iterator[str]:  # type: ignore[override]
        yield from self.content

    @validator("content", pre=True)
    def validate_content(cls, value):
        if len(value) < 1:
            raise ValueError("Must have at least 1 line of content.")

        return value

    @validator("asts", pre=True)
    def validate_asts(cls, value):
        if len(value) < 1:
            raise ValueError("Must have at least 1 AST node.")

        return value

    @property
    def begin_lineno(self) -> int:
        """
        The first line number.
        """

        return self.asts[0].lineno

    @property
    def ws_begin_lineno(self) -> int:
        """
        The first line number including backfilled whitespace lines
        (for output debugging purposes).
        """

        # NOTE: Whitespace only include when above or besides a statement;
        # not below.

        # Whitespace lines should already be present in content.
        return self.content.begin_lineno

    @property
    def end_lineno(self) -> int:
        """
        The last line number.
        """

        return self.asts[-1].end_lineno

    @property
    def location(self) -> SourceLocation:
        return self.begin_lineno, -1, self.end_lineno, -1

    def __str__(self) -> str:
        # Include whitespace lines.
        return self.to_str()

    def __repr__(self) -> str:
        # Excludes whitespace lines.
        return self.to_str(begin_lineno=self.begin_lineno)

    def to_str(self, begin_lineno: Optional[int] = None):
        begin_lineno = self.ws_begin_lineno if begin_lineno is None else begin_lineno
        content = ""
        for lineno, line in self.content.items():
            if lineno < begin_lineno:
                continue

            elif content:
                # Indent first.
                content = f"{content.rstrip()}\n"

            content = f"{content}    {lineno} {line}"

        return content


class ContractSource(BaseModel):
    """
    A contract type wrapper that enforces all the necessary
    properties needed for doing source-code processing,
    such as coverage or showing source code lines during an exception.
    """

    contract_type: ContractType
    """The contract type with AST, PCMap, and other necessary properties."""

    source: Source
    """The source code wrapper."""

    source_path: Optional[Path] = None
    """The path to the source."""

    _function_ast_cache: Dict[str, ASTNode] = {}

    @validator("contract_type", pre=True)
    def _validate_contract_type(cls, contract_type):
        if contract_type.source_id is None:
            raise ValueError("ContractType missing source_id")
        if contract_type.ast is None:
            raise ValueError("ContractType missing ast")
        if contract_type.pcmap is None:
            raise ValueError("ContractType missing pcmap")

        return contract_type

    @classmethod
    def create(cls, contract_type: ContractType, source: Source, base_path: Optional[Path] = None):
        source_id = contract_type.source_id
        if not source_id:
            raise ValueError("ContractType missing source ID")

        if base_path:
            source_path = base_path / source_id
            if not source_path.is_file():
                raise FileNotFoundError(str(source_path))

        else:
            # Not a local contract, but source is still available.
            source_path = None

        return ContractSource(contract_type=contract_type, source=source, source_path=source_path)

    @property
    def source_id(self) -> str:
        """The contract type source ID."""

        return self.contract_type.source_id  # type: ignore[return-value]

    @property
    def ast(self) -> ASTNode:
        """The contract type AST node."""

        return self.contract_type.ast  # type: ignore[return-value]

    @property
    def pcmap(self) -> PCMap:
        """The contract type PCMap."""

        return self.contract_type.pcmap  # type: ignore[return-value]

    def __repr__(self) -> str:
        return f"<{self.contract_type.source_id}::{self.contract_type.name or 'unknown'}>"

    def lookup_function(
        self, location: SourceLocation, method_id: Optional[HexBytes] = None
    ) -> Optional[Function]:
        """
        Lookup a function by location.

        Args:
            location (``SourceLocation``): The location to search.
            method_id (Optional[HexBytes]): Optionally provide a method ID
              to use to craft a nicer name. Defaults to using the combined
              lines of the function signature content.

        Returns:
            Optional[:class:`~ape.types.trace.SourceFunction`]: The function, if one is
            found.
        """

        ast = self.ast.get_defining_function(location)
        if not ast:
            return None

        signature_lines, content_lines = self._parse_function(ast)
        if not signature_lines or not content_lines:
            return None

        signature_start = ast.lineno
        offset = signature_start + len(signature_lines)

        # Check if method ID points to a calling method.
        name = None
        full_name = None
        if method_id and method_id.hex() in self._function_ast_cache:
            cached_fn = self._function_ast_cache[method_id.hex()]
            if (
                cached_fn.lineno == ast.lineno
                and cached_fn.end_lineno == ast.end_lineno
                and method_id in self.contract_type.methods
            ):
                # Is the same function. It's safe to use the method ABI name.
                method = self.contract_type.methods[method_id]
                name = method.name
                full_name = method.selector

        elif method_id and method_id in self.contract_type.methods:
            # Not in cache yet. Assume is calling.
            method = self.contract_type.methods[method_id]
            name = method.name
            full_name = method.selector
            self._function_ast_cache[method_id.hex()] = ast

        elif ast.name is not None:
            # Use the AST name.
            name = ast.name
            full_name = _strip_function(signature_lines)

        if name is None:
            # This method is not present in the ABI, maybe because it is internal.
            # Also, the name is missing from the AST node.
            # Combine the signature lines into a single string.
            full_name = _strip_function(signature_lines)
            name = full_name

            # If it looks like arguments are defined in parenthesis, remove those.
            # my_method(123) -> my_method
            if (
                "(" in name
                and ")" in name
                and full_name.index("(") < len(name) - 1 - name[::-1].index(")")
            ):
                name = full_name.split("(")[0]

        signature_dict = {signature_start + i: ln for i, ln in enumerate(signature_lines)}
        content_dict = {offset + i: ln for i, ln in enumerate(content_lines)}
        content = Content(__root__={**signature_dict, **content_dict})
        Function.update_forward_refs()

        return Function(
            ast=ast,
            content=content,
            full_name=full_name,
            name=name,
            offset=offset,
        )

    def _parse_function(self, function: ASTNode) -> Tuple[List[str], List[str]]:
        """
        Parse function AST into two groups. One being the list of
        lines making up the signature and the other being the content
        lines of the function.
        """

        start = function.lineno - 1
        end = function.end_lineno
        lines = self.source[start:end]

        content_start = None
        for child in function.children:
            # Find smallest lineno after signature-related ASTs.
            if (
                child.lineno > function.lineno
                and child.classification != ASTClassification.FUNCTION
                and (content_start is None or child.lineno < content_start)
            ):
                content_start = child.lineno

        if content_start is None:
            # Shouldn't happen, but just in case, use only the first line.
            content_start = function.lineno + 1

        offset = content_start - function.lineno
        return lines[:offset], lines[offset:]


def _strip_function(signature_lines: List[str]) -> str:
    name = "".join([x.strip() for x in signature_lines]).rstrip()

    # Strip off any common function definition prefixes, if found.
    # def my_method -> my_method
    common_prefixes = ("def ", "function ", "fn ", "func ")
    for prefix in common_prefixes:
        if not name.startswith(prefix):
            continue

        name = name.split(prefix)[-1]

    return name.rstrip(":{ \n")
