#!/usr/bin/env python3
"""Script to build and publish the package to PyPI"""

import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, check=True):
    """Run a shell command"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, check=check)
    return result.returncode == 0


def main():
    """Main function to build and publish package"""
    # Ensure we're in the project root
    project_root = Path(__file__).parent
    os.chdir(project_root)
    
    print("🚀 Starting package build and publish process...")
    
    # Clean previous builds
    print("\n📦 Cleaning previous builds...")
    run_command("rm -rf build/ dist/ *.egg-info/")
    
    # Install build dependencies
    print("\n📋 Installing build dependencies...")
    if not run_command("pip install build twine"):
        print("❌ Failed to install build dependencies")
        return 1
    
    # Build the package
    print("\n🔨 Building package...")
    if not run_command("python -m build"):
        print("❌ Failed to build package")
        return 1
    
    # Check the built package
    print("\n🔍 Checking package...")
    if not run_command("twine check dist/*"):
        print("❌ Package check failed")
        return 1
    
    print("\n✅ Package built successfully!")
    print("\n📁 Built files:")
    run_command("ls -la dist/")
    
    # Ask user if they want to upload to PyPI
    response = input("\n🚀 Do you want to upload to PyPI? (y/N): ").strip().lower()
    if response in ['y', 'yes']:
        print("\n📤 Uploading to PyPI...")
        print("Note: You'll need to enter your PyPI credentials")
        if run_command("twine upload dist/*"):
            print("\n🎉 Package successfully uploaded to PyPI!")
        else:
            print("\n❌ Failed to upload to PyPI")
            return 1
    else:
        print("\n📦 Package is ready for upload. Use 'twine upload dist/*' when ready.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())