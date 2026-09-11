from setuptools import setup, find_packages

setup(
    name="linagent",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    package_data={"linagent.web": ["static/*"]},
    install_requires=[
        "pydantic>=2.0.0",
        "openai>=1.0.0",
        "requests>=2.28.0",
        "fastapi>=0.100.0",
        "uvicorn>=0.20.0",
    ],
    entry_points={
        "console_scripts": [
            "linagent = linagent.cli.main:main",
        ],
    },
)
