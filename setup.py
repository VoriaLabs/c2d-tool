from setuptools import setup, find_packages

setup(
    name="c2d-tool",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "ezdxf",
    ],
    entry_points={
        "console_scripts": [
            "c2d-tool=c2d_tool.main:main",
        ],
    },
)
