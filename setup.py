from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="miot-mcp",
    version="1.0.3",
    author="Javen Yan",
    author_email="2023335616@qq.com",
    description="Mijia smart device MCP server, providing device discovery, property read/write, action invoke and other functions",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/javen-yan/miot-mcp",      
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Home Automation",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "setuptools>=80.9.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    keywords="xiaomi mijia iot smart-home mcp automation",
    project_urls={
        "Bug Reports": "https://github.com/javen-yan/miot-mcp/issues",
        "Source": "https://github.com/javen-yan/miot-mcp",
        "Documentation": "https://github.com/javen-yan/miot-mcp#readme",
    },
)