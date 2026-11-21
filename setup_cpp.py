import sys
import torch
from setuptools import setup, find_packages
from torch.utils.cpp_extension import BuildExtension, CppExtension

setup(
    name="imf_cpp_ops",
    version="1.0.0",
    ext_modules=[
        CppExtension(
            name="imf.imf_cpp_ops",
            sources=["csrc/imf_extension_bindings.cpp"],
            extra_compile_args=["-O3", "-std=c++20"],
        )
    ],
    cmdclass={
        "build_ext": BuildExtension
    }
)
