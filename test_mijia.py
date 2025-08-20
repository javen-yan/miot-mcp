from adapter.mijia_adapter import MijiaAdapter
import asyncio


async def test_mijia_adapter():
    adapter = MijiaAdapter()
    await adapter.connect()
    
    devices = await adapter.discover_devices()
    
    actions = await adapter.get_device_actions(devices[0].did)
    print(actions)

    props = await adapter.get_device_properties(devices[0].did)
    print(props)

    deviceNum = adapter.device_count
    print(deviceNum)


if __name__ == "__main__":
    asyncio.run(test_mijia_adapter())