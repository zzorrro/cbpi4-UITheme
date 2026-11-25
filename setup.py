from setuptools import setup, find_packages

setup(
    name="cbpi4-UITheme",
    version="1.0.0",
    description="Color and font settings for the CraftBeerPi4 interface, editable in Settings",
    author="zzorrro",
    url="https://github.com/zzorrro/cbpi4-UITheme",
    license="MIT",
    packages=find_packages(),
    include_package_data=True,
    package_data={"": ["*.yaml"]},
)
