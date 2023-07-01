import contextlib
import subprocess
from collections import defaultdict
from functools import cached_property
from pathlib import Path

import huffc
from ape.api import CompilerAPI, PluginConfig
from ape.exceptions import CompilerError
from ethpm_types import ContractType


class HuffConfig(PluginConfig):
    version: str | None = None


class HuffCompiler(CompilerAPI):
    @property
    def name(self):
        return "huff"

    @property
    def config(self):
        return self.config_manager.get_config(self.name)

    @cached_property
    def version(self):
        with huffc.VersionManager() as hvm:
            version = str(self.config.version or max(hvm.fetch_remote_versions()))

            if hvm.get_executable(version) is None:
                hvm.install(version)

            return version

    def get_versions(self, all_paths):
        with huffc.VersionManager() as hvm:
            return hvm.fetch_remote_versions()

    def get_compiler_settings(self, contract_filepaths, base_path=None):
        return defaultdict(dict)

    def get_version_map(self, contract_filepaths, base_path=None):
        return {self.version: set(contract_filepaths)}

    def compile(self, contract_filepaths, base_path):
        artifacts = {}
        for path in [file.relative_to(Path.cwd()) for file in contract_filepaths]:
            try:
                artifacts.update(huffc.compile([path], version=self.version))
            except subprocess.CalledProcessError as exc:
                msg = exc.stderr.decode().split("\n", 1)[-1]
                if 'Error: Missing Macro Definition For "MAIN"' not in msg:
                    raise CompilerError(msg)

        def kind_to_type(kind):
            match kind:
                case "Address" | "Bytes" | "Bool" | "String":
                    return kind.lower()
                case {"FixedBytes": size}:
                    return f"bytes{size}"
                case {"Uint": _} | {"Int": _}:
                    typ, size = kind.popitem()
                    return f"{typ.lower()}{size}"
                case {"Array": [k, size]}:
                    suffix = "".join([f"[{s or ''}]" for s in size])
                    return f"{kind_to_type(k)}" + suffix
                case _:
                    raise Exception("Unknown type.")

        def format(abi):
            result = []

            for typ in ("constructor", "fallback", "receive"):
                if not (item := abi[typ]):
                    continue

                result += [
                    {
                        "type": typ,
                        "inputs": [
                            {"name": inp["name"], "type": kind_to_type(inp["kind"])}
                            for inp in item.get("inputs", [])
                        ],
                        "stateMutability": item.get("state_mutability", "payable"),
                    }
                ]

            for item in abi["functions"].values():
                item["type"] = "function"

                item["stateMutability"] = item["state_mutability"].lower()
                item["inputs"] = [
                    {"name": inp["name"], "type": kind_to_type(inp["kind"])}
                    for inp in item["inputs"]
                ]
                item["outputs"] = [
                    {"name": inp["name"], "type": kind_to_type(inp["kind"])}
                    for inp in item["outputs"]
                ]
                result.append(item)

            for item in abi["events"].values():
                item["type"] = "event"

                item["inputs"] = [
                    {
                        "name": inp["name"],
                        "type": kind_to_type(inp["kind"]),
                        "indexed": inp["indexed"],
                    }
                    for inp in item["inputs"]
                ]
                result.append(item)

            return result

        for file, artifact in artifacts.items():
            artifact["contractName"] = Path(file).stem
            artifact["sourceId"] = Path.cwd().joinpath(file).relative_to(base_path).as_posix()
            artifact["deploymentBytecode"] = {"bytecode": artifact["bytecode"]}
            artifact["runtimeBytecode"] = {"bytecode": artifact["runtime"]}
            artifact["abi"] = format(artifact["abi"])

        return [ContractType.parse_obj(artifact) for artifact in artifacts.values()]

    def get_imports(self, contract_filepaths, base_path):
        artifacts = {}
        for path in [file.relative_to(Path.cwd()) for file in contract_filepaths]:
            with contextlib.suppress(subprocess.CalledProcessError):
                artifacts.update(huffc.compile([path], version=self.version))

        def collect(dependencies):
            result = []
            for dependency in dependencies:
                if dependency["dependencies"]:
                    result.extend(collect(dependency["dependencies"]))
                else:
                    result.append(
                        Path.cwd().joinpath(dependency["path"]).relative_to(base_path).as_posix()
                    )
            return result

        return {
            Path.cwd()
            .joinpath(file)
            .relative_to(base_path)
            .as_posix(): sorted(collect(artifact["file"]["dependencies"]))
            for file, artifact in artifacts.items()
        }
