from ape import plugins

from ape_huff.compiler import HuffCompiler, HuffConfig


@plugins.register(plugins.Config)
def config_class():
    return HuffConfig


@plugins.register(plugins.CompilerPlugin)
def register_compiler():
    return (".huff",), HuffCompiler
