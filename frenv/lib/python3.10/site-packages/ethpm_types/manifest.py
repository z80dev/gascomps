from typing import Dict, List, Optional

from pydantic import Field, root_validator, validator

from .base import BaseModel
from .contract_type import BIP122_URI, ContractInstance, ContractType
from .source import Compiler, Source
from .utils import Algorithm, AnyUrl

ALPHABET = set("abcdefghijklmnopqrstuvwxyz")
NUMBERS = set("0123456789")


class PackageName(str):
    """
    A human readable name for this package.
    """

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            pattern="^[a-z][-a-z0-9]{0,254}$",
            examples=["my-token", "safe-math", "nft"],
        )

    @classmethod
    def __get_validators__(cls):
        yield cls.check_length
        yield cls.check_first_character
        yield cls.check_valid_characters

    @classmethod
    def check_length(cls, value):
        assert 0 < len(value) < 256, "Length must be between 1 and 255"
        return value

    @classmethod
    def check_first_character(cls, value):
        assert value[0] in ALPHABET, "First character in name must be a-z"
        return value

    @classmethod
    def check_valid_characters(cls, value):
        assert set(value) < ALPHABET.union(NUMBERS).union(
            "-"
        ), "Characters in name must be one of a-z or 0-9 or '-'"
        return value

    def __repr__(self):
        return f"{self.__class__.__name__}({super().__repr__()})"


class PackageMeta(BaseModel):
    """
    Important data that is not integral to installation
    but should be included when publishing.
    """

    authors: Optional[List[str]] = None
    """A list of human readable names for the authors of this package."""

    license: Optional[str] = None
    """
    The license associated with this package.
    This value should conform to the SPDX format.
    Packages should include this field.
    If a file Source Object defines its own license, that license takes
    precedence for that particular file over this package-scoped meta license.
    """

    description: Optional[str] = None
    """Additional detail that may be relevant for this package."""

    keywords: Optional[List[str]] = None
    """Relevant keywords related to this package."""

    links: Optional[Dict[str, AnyUrl]] = None
    """
    URIs to relevant resources associated with this package.
    When possible, authors should use the following keys for the following common resources.
    """


class PackageManifest(BaseModel):
    """
    A data format describing a smart contract software package.

    `EIP-2678 <https://eips.ethereum.org/EIPS/eip-2678#ethpm-manifest-version>`__
    """

    manifest: str = "ethpm/3"
    """The specification version that the project conforms to."""

    name: Optional[PackageName] = None
    """A human-readable name for the package."""

    version: Optional[str] = None
    """The version of the release, which should be SemVer."""

    meta: Optional[PackageMeta] = None
    """
    Important data that is not integral to installation
    but should be included when publishing.
    **NOTE**: All published projects *should* include
    ``meta``.
    """

    sources: Optional[Dict[str, Source]] = None
    """
    The sources field defines a source tree that should comprise the full source tree
    necessary to recompile the contracts contained in this release.
    """

    contract_types: Optional[Dict[str, ContractType]] = Field(None, alias="contractTypes")
    """
    :class:`~ethpm_types.contract_type.ContractType` objects that have been included
    in this release.

      * Should only include types that can be found in the sources.
      * Should not include types from dependencies.
      * Should not include abstracts.
    """

    compilers: Optional[List[Compiler]] = None
    """
    Information about the compilers and their settings that have been
    used to generate the various contractTypes included in this release.
    """

    deployments: Optional[Dict[BIP122_URI, Dict[str, ContractInstance]]] = None
    """
    Information for the chains on which this release has
    :class:`~ethpm_types.contract_type.ContractInstance` references as well as the
    :class:`~ethpm_types.contract_type.ContractType` definitions and other deployment
    details for those deployed contract instances. The set of chains defined by the BIP122
    URI keys for this object must be unique. There cannot be two different URI keys in a
    deployments field representing the same blockchain. The value of the URIs is a dictionary
    mapping the contract instance names to the instance themselves. The contract instance names
    must be unique across all other contract instances for the given chain.
    """

    dependencies: Optional[Dict[PackageName, AnyUrl]] = Field(None, alias="buildDependencies")
    """
    A mapping of EthPM packages that this project depends on.
    The values must be content-addressable URIs that conforms to the same
    manifest version as ``manifest``.
    """

    @root_validator
    def check_valid_manifest_version(cls, values):
        # NOTE: We only support v3 (EIP-2678) of the ethPM spec currently
        if values["manifest"] != "ethpm/3":
            raise ValueError("Only ethPM V3 (EIP-2678) supported.")

        return values

    @root_validator
    def check_both_version_and_name(cls, values):
        if ("name" in values or "version" in values) and (
            "name" not in values or "version" not in values
        ):
            raise ValueError("Both `name` and `version` must be present if either is specified.")

        return values

    @root_validator
    def check_contract_source_ids(cls, values):
        contract_types = values.get("contract_types", {}) or {}
        for alias in contract_types:
            source_id = values["contract_types"][alias].source_id
            sources = values.get("sources", {}) or {}
            if source_id and (source_id not in sources):
                raise ValueError(f"'{source_id}' missing from `sources`.")

        return values

    @validator("contract_types")
    def add_name_to_contract_types(cls, values):
        aliases = list(values.keys())
        # NOTE: Must manually inject names to types here
        for alias in aliases:
            if not values[alias]:
                values[alias].name = alias
            # else: contractName != contractAlias (key used in `contractTypes` dict)

        return values

    def __getattr__(self, attr_name: str):
        # NOTE: **must** raise `AttributeError` or return here, or else Python breaks
        if self.contract_types and attr_name in self.contract_types:
            return self.contract_types[attr_name]

        else:
            raise AttributeError(f"{self.__class__.__name__} has no contract type '{attr_name}'")

    def dict(self, *args, **kwargs) -> Dict:
        res = super().dict()
        sources = res.get("sources", {})
        for source_id, src in sources.items():
            if "content" in src and isinstance(src["content"], dict):
                content = "\n".join(src["content"].values())
                if content and not content.endswith("\n"):
                    content = f"{content}\n"

                src["content"] = content

            elif "content" in src and src["content"] is None:
                src["content"] = ""

            if (
                "checksum" in src
                and "algorithm" in src["checksum"]
                and isinstance(src["checksum"]["algorithm"], Algorithm)
            ):
                src["checksum"]["algorithm"] = src["checksum"]["algorithm"].value

        return res
