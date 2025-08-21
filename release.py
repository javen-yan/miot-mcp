#!/usr/bin/env python3
"""Script to help create a new release"""

import json
import re
import subprocess
import sys
from pathlib import Path


def get_current_version():
    """Get current version from setup.py"""
    setup_py = Path("setup.py")
    if setup_py.exists():
        content = setup_py.read_text()
        match = re.search(r'version="([^"]+)"', content)
        if match:
            return match.group(1)
    return None


def update_version_in_file(file_path, old_version, new_version):
    """Update version in a specific file"""
    file_path = Path(file_path)
    if not file_path.exists():
        print(f"⚠️  File {file_path} not found, skipping...")
        return False
    
    content = file_path.read_text()
    
    if file_path.suffix == '.json':
        # Handle JSON files
        try:
            data = json.loads(content)
            if 'version' in data:
                data['version'] = new_version
                file_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
                print(f"✅ Updated {file_path}")
                return True
        except json.JSONDecodeError:
            print(f"❌ Failed to parse JSON in {file_path}")
            return False
    else:
        # Handle Python files
        patterns = [
            (rf'version="{re.escape(old_version)}"', f'version="{new_version}"'),
            (rf"version='{re.escape(old_version)}'", f"version='{new_version}'"),
        ]
        
        updated = False
        for pattern, replacement in patterns:
            if re.search(pattern, content):
                content = re.sub(pattern, replacement, content)
                updated = True
        
        if updated:
            file_path.write_text(content)
            print(f"✅ Updated {file_path}")
            return True
        else:
            print(f"⚠️  No version found in {file_path}")
            return False


def run_command(cmd):
    """Run a shell command"""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Command failed: {result.stderr}")
        return False
    return True


def validate_version(version):
    """Validate version format"""
    pattern = r'^\d+\.\d+\.\d+$'
    return re.match(pattern, version) is not None


def main():
    """Main function"""
    print("🚀 Release Helper Script")
    print("=" * 50)
    
    # Get current version
    current_version = get_current_version()
    if current_version:
        print(f"📋 Current version: {current_version}")
    else:
        print("❌ Could not determine current version")
        return 1
    
    # Get new version from user
    while True:
        new_version = input(f"\n📝 Enter new version (current: {current_version}): ").strip()
        if not new_version:
            print("❌ Version cannot be empty")
            continue
        if not validate_version(new_version):
            print("❌ Invalid version format. Use MAJOR.MINOR.PATCH (e.g., 1.2.3)")
            continue
        if new_version == current_version:
            print("❌ New version must be different from current version")
            continue
        break
    
    print(f"\n🔄 Updating version from {current_version} to {new_version}...")
    
    # Files to update
    files_to_update = [
        "setup.py",
        "pyproject.toml",
        "mcp_server/server_config.json"
    ]
    
    # Update version in files
    success_count = 0
    for file_path in files_to_update:
        if update_version_in_file(file_path, current_version, new_version):
            success_count += 1
    
    if success_count == 0:
        print("❌ No files were updated")
        return 1
    
    print(f"\n✅ Updated {success_count}/{len(files_to_update)} files")
    
    # Ask if user wants to commit and create release
    response = input("\n🔧 Do you want to commit changes and create a git tag? (y/N): ").strip().lower()
    if response in ['y', 'yes']:
        # Commit changes
        if not run_command("git add ."):
            return 1
        
        commit_msg = f"Bump version to {new_version}"
        if not run_command(f'git commit -m "{commit_msg}"'):
            return 1
        
        # Create tag
        tag_name = f"v{new_version}"
        if not run_command(f'git tag {tag_name}'):
            return 1
        
        print(f"\n✅ Created commit and tag {tag_name}")
        
        # Ask about pushing
        push_response = input("\n🚀 Do you want to push changes and tag to remote? (y/N): ").strip().lower()
        if push_response in ['y', 'yes']:
            if run_command("git push origin main") and run_command(f"git push origin {tag_name}"):
                print(f"\n🎉 Successfully pushed version {new_version}!")
                print("\n📋 Next steps:")
                print("1. Go to GitHub repository")
                print(f"2. Create a new release using tag {tag_name}")
                print("3. GitHub Actions will automatically publish to PyPI")
            else:
                return 1
        else:
            print(f"\n📋 Changes committed locally with tag {tag_name}")
            print("Run the following commands when ready to push:")
            print(f"  git push origin main")
            print(f"  git push origin {tag_name}")
    else:
        print("\n📋 Version updated in files. Remember to commit changes:")
        print(f"  git add .")
        print(f'  git commit -m "Bump version to {new_version}"')
        print(f"  git tag v{new_version}")
        print(f"  git push origin main")
        print(f"  git push origin v{new_version}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())