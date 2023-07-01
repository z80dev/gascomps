from enum import Enum
from typing import Dict, Iterator, List, Optional, Union

from pydantic import root_validator

from ethpm_types.base import BaseModel
from ethpm_types.sourcemap import SourceMapItem
from ethpm_types.utils import SourceLocation


class ASTClassification(Enum):
    UNCLASSIFIED = 0
    """Unclassified AST type (default)."""

    FUNCTION = 1
    """ASTTypes related to defining a function."""


class ASTNode(BaseModel):
    name: Optional[str] = None
    """
    The node's name if it has one, such as a function name.
    """

    ast_type: str
    """
    The compiler-given AST node type, such as ``FunctionDef``.
    """

    classification: ASTClassification = ASTClassification.UNCLASSIFIED
    """
    A generic classification of what type of AST this is.
    """

    doc_str: Optional[Union[str, "ASTNode"]] = None
    """
    Documentation for the node.
    """

    src: SourceMapItem
    """
    The source offset item.
    """

    lineno: int = -1
    """
    The start line number in the source.
    """

    end_lineno: int = -1
    """
    The line number where the AST node ends.
    """

    col_offset: int = -1
    """
    The offset of the column start.
    """

    end_col_offset: int = -1
    """
    The offset when the column ends.
    """

    children: List["ASTNode"] = []
    """
    All sub-AST nodes within this one.
    """

    @root_validator(pre=True)
    def validate_node(cls, val):
        src = cls._validate_src(val)

        # Handle `ast_type`.
        if "nodeType" in val and "ast_type" not in val:
            val["ast_type"] = val.pop("nodeType")

        return {
            "doc_str": val.get("doc_string"),
            "children": cls.find_children(val),
            **val,
            "src": src,
        }

    @classmethod
    def _validate_src(cls, val: Dict) -> SourceMapItem:
        src = val.get("src")
        if src and isinstance(src, str):
            src = SourceMapItem.parse_str(src)

        elif isinstance(src, dict):
            src = SourceMapItem.parse_obj(src)

        elif not isinstance(src, SourceMapItem):
            raise TypeError(type(src))

        return src

    @classmethod
    def find_children(cls, node) -> List["ASTNode"]:
        children = []

        def add_child(data):
            data["children"] = cls.find_children(data)
            child = cls.parse_obj(data)
            children.append(child)

        for value in node.values():
            if isinstance(value, dict) and ("ast_type" in value or "nodeType" in value):
                add_child(value)

            elif isinstance(value, list):
                for _val in value:
                    if isinstance(_val, dict) and ("ast_type" in _val or "nodeType" in _val):
                        add_child(_val)

        return children

    @property
    def line_numbers(self) -> SourceLocation:
        """
        The values needed for constructing the line numbers for this node
        in the form ``[lineno, col_offset, end_lineno, end_col_offset]``.
        """

        return self.lineno, self.col_offset, self.end_lineno, self.end_col_offset

    @property
    def functions(self) -> List["ASTNode"]:
        """
        All function nodes defined at this level.

        **NOTE**: This is only populated on a ``Module`` AST node.
        """

        return [n for n in self.children if n.ast_type == "FunctionDef"]

    def __repr__(self) -> str:
        return str(self)

    def __str__(self):
        num_children = len(self.children)
        stats = "leaf" if num_children == 0 else f"children={num_children}"
        return f"<{self.ast_type}Node {stats}>"

    def iter_nodes(self) -> Iterator["ASTNode"]:
        """
        Yield through all nodes in the tree, including this one.
        """

        yield self
        for node in self.children:
            yield from node.iter_nodes()

    def get_node(self, src: SourceMapItem) -> Optional["ASTNode"]:
        """
        Get a node by source.

        Args:
            src (:class:`~ethpm_types.sourcemap.SourceMapItem`): The source map
              item to seek in the AST.

        Returns:
            Optional[``ASTNode``]: The matching node, if found, else ``None``.
        """

        if self.src.start == src.start and (self.src.length or 0) == (src.length or 0):
            return self

        for child in self.children:
            node = child.get_node(src)
            if node:
                return node

        return None

    def get_nodes_at_line(self, line_numbers: SourceLocation) -> List["ASTNode"]:
        """
        Get the AST nodes for the given line number combination

        Args:
            line_numbers (``SourceLocation``): A tuple in the form of
              [lineno, col_offset, end_lineno, end_col_offset].

        Returns:
            List[``ASTNode``]: All matching nodes.
        """

        nodes = []
        if len(line_numbers) != 4:
            raise ValueError(
                "Line numbers should be given in form of "
                "`(lineno, col_offset, end_lineno, end_coloffset)`"
            )

        if all(x == y for x, y in zip(self.line_numbers, line_numbers)):
            nodes.append(self)

        for child in self.children:
            subs = child.get_nodes_at_line(line_numbers)
            nodes.extend(subs)

        return nodes

    def get_defining_function(self, line_numbers: SourceLocation) -> Optional["ASTNode"]:
        """
        Get the function that defines the given line numbers.

        Args:
            line_numbers (``SourceLocation``): A tuple in the form of
              [lineno, col_offset, end_lineno, end_col_offset].

        Returns:
            Optional[``ASTNode``]: The function definition AST node if found,
              else ``None``.
        """

        for function in self.functions:
            if function.get_nodes_at_line(line_numbers):
                return function

        return None
