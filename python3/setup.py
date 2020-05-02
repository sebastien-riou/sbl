import setuptools


setuptools.setup(
    name="pysbl",
    version="0.3.0",
    author="Sebastien Riou",
    author_email="matic@nimp.co.uk",
    description="Library for controlling embedded devices using SBL",
    long_description = """
    Library for controlling embedded devices using SBL
    """,
    long_description_content_type="text/markdown",
    url="https://github.com/sebastien-riou/sbl",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
)
