#!/usr/bin/env python3
"""FastMCP server test script

Test FastMCP-based Mijia MCP server functionality.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add project root directory to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.mijia_config import load_mijia_config

default_config = load_mijia_config()

# Configure logging
logging.basicConfig(level=default_config.log_level)
logger = logging.getLogger(__name__)


async def test_fastmcp_server():
    """Test FastMCP server"""
    print("=== FastMCP Server Test ===")
    
    server_script = str(project_root / "mcp_server" / "mcp_server.py")
    
    try:
        # Start server process
        process = await asyncio.create_subprocess_exec(
            sys.executable, server_script,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        print("✓ FastMCP server process started successfully")
        
        # Wait for server initialization
        await asyncio.sleep(1)
        
        # Test 1: Send initialization request
        print("\n1. Testing initialization request...")
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0"
                }
            }
        }
        
        if process.stdin:
            request_data = json.dumps(init_request) + "\n"
            process.stdin.write(request_data.encode())
            await process.stdin.drain()
            print("✓ Initialization request sent")
            
            # Read response
            if process.stdout:
                try:
                    response_data = await asyncio.wait_for(
                        process.stdout.readline(), timeout=5.0
                    )
                    if response_data:
                        response = json.loads(response_data.decode().strip())
                        print(f"✓ Received initialization response: {response.get('result', response)}")
                        
                        # Send initialized notification
                        initialized_notification = {
                            "jsonrpc": "2.0",
                            "method": "notifications/initialized",
                            "params": {}
                        }
                        notification_data = json.dumps(initialized_notification) + "\n"
                        process.stdin.write(notification_data.encode())
                        await process.stdin.drain()
                        print("✓ Initialized notification sent")
                        
                        # Wait for server to process notification
                        await asyncio.sleep(0.5)
                        
                    else:
                        print("⚠ No initialization response received")
                except asyncio.TimeoutError:
                    print("⚠ Initialization response timeout")
                except json.JSONDecodeError as e:
                    print(f"⚠ Failed to parse initialization response: {e}")
        
        # Test 2: Send tool list request
        print("\n2. Testing tool list request...")
        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        
        if process.stdin:
            request_data = json.dumps(tools_request) + "\n"
            process.stdin.write(request_data.encode())
            await process.stdin.drain()
            print("✓ Tool list request sent")
            
            # Read response
            if process.stdout:
                try:
                    response_data = await asyncio.wait_for(
                        process.stdout.readline(), timeout=5.0
                    )
                    if response_data:
                        response = json.loads(response_data.decode().strip())
                        if "result" in response and "tools" in response["result"]:
                            tools = response["result"]["tools"]
                            print(f"✓ Received {len(tools)} tools:")
                            for tool in tools:
                                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
                        else:
                            print(f"⚠ Tool list response format error: {response}")
                    else:
                        print("⚠ No tool list response received")
                except asyncio.TimeoutError:
                    print("⚠ Tool list response timeout")
                except json.JSONDecodeError as e:
                    print(f"⚠ Failed to parse tool list response: {e}")
        
        # Test 3: Call ping tool
        print("\n3. Testing ping tool call...")
        ping_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "ping",
                "arguments": {
                    "message": "test message"
                }
            }
        }
        
        if process.stdin:
            request_data = json.dumps(ping_request) + "\n"
            process.stdin.write(request_data.encode())
            await process.stdin.drain()
            print("✓ Ping tool call request sent")
            
            # Read response
            if process.stdout:
                try:
                    response_data = await asyncio.wait_for(
                        process.stdout.readline(), timeout=5.0
                    )
                    if response_data:
                        response = json.loads(response_data.decode().strip())
                        if "result" in response:
                            print(f"✓ Ping tool call successful: {response['result']}")
                        else:
                            print(f"⚠ Ping tool call response error: {response}")
                    else:
                        print("⚠ No ping tool call response received")
                except asyncio.TimeoutError:
                    print("⚠ Ping tool call response timeout")
                except json.JSONDecodeError as e:
                    print(f"⚠ Failed to parse ping tool call response: {e}")
        
        # Close process
        if process.stdin:
            process.stdin.close()
        
        # Wait for process to end
        try:
            await asyncio.wait_for(process.wait(), timeout=5.0)
            print(f"\n✓ Server process ended normally, exit code: {process.returncode}")
        except asyncio.TimeoutError:
            print("\n⚠ Server process did not end in time, force terminating")
            process.terminate()
            await process.wait()
        
        # Check stderr output
        if process.stderr:
            stderr_data = await process.stderr.read()
            if stderr_data:
                stderr_text = stderr_data.decode().strip()
                if stderr_text:
                    print(f"\nServer log output:\n{stderr_text}")
        
        return True
        
    except Exception as e:
        print(f"✗ FastMCP server test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Main test function"""
    print("Starting FastMCP server functionality test...\n")
    
    success = await test_fastmcp_server()
    
    print(f"\n{'='*60}")
    if success:
        print("🎉 FastMCP server test completed!")
    else:
        print("⚠ FastMCP server test failed, please check related issues.")
    print(f"{'='*60}")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)