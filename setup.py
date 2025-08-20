from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="miot-agent",
    version="2.0.0",
    author="Javen Yan",
    author_email="2023335616@qq.com",
    description="基于 MijiaAPI 的米家设备智能控制代理，提供标准化的 AI Agent 工具接口",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/javen-yan/miot-agent",      
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
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "black>=22.0.0",
            "flake8>=5.0.0"
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    keywords="xiaomi mijia iot smart-home ai-agent automation",
    project_urls={
        "Bug Reports": "https://github.com/javen-yan/miot-agent/issues",
        "Source": "https://github.com/javen-yan/miot-agent",
        "Documentation": "https://github.com/javen-yan/miot-agent#readme",
    },
)