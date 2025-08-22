#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mijia Adapter 接口使用示例

本示例展示了如何使用 MijiaAdapter 类来：
1. 连接到米家云服务
2. 发现设备
3. 获取设备属性和动作
4. 读取和设置设备属性值
5. 执行设备动作
6. 获取家庭和场景信息
"""

import asyncio
import logging
from adapter.mijia_adapter import MijiaAdapter

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

class MijiaAdapterDemo:
    """Mijia Adapter 使用示例类"""
    
    def __init__(self):
        self.adapter = MijiaAdapter()
        self.devices = []
    
    async def demo_connection(self) -> bool:
        """演示连接功能"""
        logger.info("=== 连接到米家云服务 ===")
        
        try:
            success = await self.adapter.connect()
            if success:
                logger.info(f"✅ 连接成功！连接状态: {self.adapter.connected}")
                return True
            else:
                logger.error("❌ 连接失败")
                return False
        except Exception as e:
            logger.error(f"❌ 连接异常: {e}")
            return False
    
    async def demo_device_discovery(self) -> bool:
        """演示设备发现功能"""
        logger.info("\n=== 发现设备 ===")
        
        try:
            self.devices = await self.adapter.discover_devices()
            logger.info(f"✅ 发现 {len(self.devices)} 个设备")
            
            for i, device in enumerate(self.devices):
                logger.info(f"  设备 {i+1}: {device.name} (ID: {device.did}, 型号: {device.model})")
            
            return len(self.devices) > 0
        except Exception as e:
            logger.error(f"❌ 设备发现失败: {e}")
            return False
    
    async def demo_device_properties(self, device_index: int = 0):
        """演示获取设备属性"""
        if not self.devices or device_index >= len(self.devices):
            logger.warning("⚠️ 没有可用设备或设备索引无效")
            return
        
        device = self.devices[device_index]
        logger.info(f"\n=== 获取设备属性: {device.name} ===")
        
        try:
            properties = await self.adapter.get_device_properties(device.did)
            logger.info(f"✅ 获取到 {len(properties)} 个属性:")

            for prop in properties:
                logger.info(f"  属性: {prop.name} ({prop.desc})")
                logger.info(f"    类型: {prop.type}, 权限: {prop.rw}, 单位: {prop.unit}")
                if prop.range:
                    logger.info(f"    范围: {prop.range}")
                if prop.value_list:
                    logger.info(f"    可选值: {prop.value_list}")
                logger.info(f"    方法: siid={prop.method.get('siid')}, piid={prop.method.get('piid')}")
                logger.info("")
            
            return properties
        except Exception as e:
            logger.error(f"❌ 获取设备属性失败: {e}")
            return []
    
    async def demo_device_actions(self, device_index: int = 0):
        """演示获取设备动作"""
        if not self.devices or device_index >= len(self.devices):
            logger.warning("⚠️ 没有可用设备或设备索引无效")
            return
        
        device = self.devices[device_index]
        logger.info(f"\n=== 获取设备动作: {device.name} ===")
        
        try:
            actions = await self.adapter.get_device_actions(device.did)
            logger.info(f"✅ 获取到 {len(actions)} 个动作:")

            for action in actions:
                logger.info(f"  动作: {action.name} ({action.desc})")
                logger.info(f"    方法: siid={action.method.get('siid')}, aiid={action.method.get('aiid')}")
                if hasattr(action, 'in_params') and action.in_params:
                    logger.info(f"    输入参数: {action.in_params}")
                if hasattr(action, 'out_params') and action.out_params:
                    logger.info(f"    输出参数: {action.out_params}")
                logger.info("")
            
            return actions
        except Exception as e:
            logger.error(f"❌ 获取设备动作失败: {e}")
            return []
    
    async def demo_property_operations(self, device_index: int = 0):
        """演示属性读取和设置操作"""
        if not self.devices or device_index >= len(self.devices):
            logger.warning("⚠️ 没有可用设备或设备索引无效")
            return
        
        device = self.devices[device_index]
        logger.info(f"\n=== 属性操作示例: {device.name} ===")
        
        try:
            # 获取设备属性列表
            properties = await self.adapter.get_device_properties(device.did)
            
            # 找一个可读的属性进行演示
            readable_props = [p for p in properties if 'r' in p.rw.lower()]
            if readable_props:
                prop = readable_props[0]
                siid = prop.method.get('siid')
                piid = prop.method.get('piid')
                
                logger.info(f"📖 读取属性: {prop.name}")
                try:
                    value = await self.adapter.get_property_value(device.did, siid, piid)
                    logger.info(f"✅ 属性值: {value}")
                except Exception as e:
                    logger.error(f"❌ 读取属性失败: {e}")
            
            # 找一个可写的属性进行演示（谨慎操作）
            writable_props = [p for p in properties if 'w' in p.rw.lower()]
            if writable_props:
                prop = writable_props[0]
                logger.info(f"📝 发现可写属性: {prop.name} (类型: {prop.type})")
                logger.info("⚠️ 为了安全，此demo不会实际修改设备属性")
                logger.info(f"   如需设置，可调用: await adapter.set_property_value('{device.did}', {prop.method.get('siid')}, {prop.method.get('piid')}, value)")
        
        except Exception as e:
            logger.error(f"❌ 属性操作失败: {e}")
    
    async def demo_device_status(self, device_index: int = 0):
        """演示获取设备状态"""
        if not self.devices or device_index >= len(self.devices):
            logger.warning("⚠️ 没有可用设备或设备索引无效")
            return
        
        device = self.devices[device_index]
        logger.info(f"\n=== 获取设备状态: {device.name} ===")
        
        try:
            status = await self.adapter.get_device_status(device.did)
            logger.info("✅ 设备状态信息:")
            for key, value in status.items():
                logger.info(f"  {key}: {value}")
        except Exception as e:
            logger.error(f"❌ 获取设备状态失败: {e}")
    
    async def demo_homes_and_scenes(self):
        """演示获取家庭和场景信息"""
        logger.info("\n=== 获取家庭信息 ===")
        
        try:
            homes = await self.adapter.get_homes()
            logger.info(f"✅ 获取到 {len(homes)} 个家庭:")
            
            for home in homes:
                home_id = home.get('id', 'unknown')
                home_name = home.get('name', 'unnamed')
                logger.info(f"  家庭: {home_name} (ID: {home_id})")
                
                # 获取该家庭的场景
                try:
                    scenes = await self.adapter.get_scenes_list(home_id)
                    logger.info(f"    场景数量: {len(scenes)}")
                    for scene in scenes[:3]:  # 只显示前3个场景
                        scene_name = scene.get('name', 'unnamed')
                        scene_id = scene.get('id', 'unknown')
                        logger.info(f"      场景: {scene_name} (ID: {scene_id})")
                except Exception as e:
                    logger.warning(f"    获取场景失败: {e}")
        
        except Exception as e:
            logger.error(f"❌ 获取家庭信息失败: {e}")
    
    async def demo_refresh_all_status(self):
        """演示刷新所有设备状态"""
        logger.info("\n=== 刷新所有设备状态 ===")
        
        try:
            all_status = await self.adapter.refresh_all_device_status()
            logger.info(f"✅ 成功刷新 {len(all_status)} 个设备的状态")
            
            # 显示缓存的状态信息
            cached_status = self.adapter.get_all_cached_device_status()
            logger.info(f"📦 缓存中有 {len(cached_status)} 个设备状态")
            logger.info(f"🕒 最后更新时间: {self.adapter.last_status_update}")
        
        except Exception as e:
            logger.error(f"❌ 刷新设备状态失败: {e}")
    
    async def demo_disconnect(self):
        """演示断开连接"""
        logger.info("\n=== 断开连接 ===")
        
        try:
            await self.adapter.disconnect()
            logger.info(f"✅ 已断开连接，连接状态: {self.adapter.connected}")
        except Exception as e:
            logger.error(f"❌ 断开连接失败: {e}")
    
    async def run_full_demo(self):
        """运行完整的演示"""
        logger.info("🚀 开始 Mijia Adapter 完整演示")
        logger.info("=" * 50)
        
        try:
            # 1. 连接
            if not await self.demo_connection():
                return
            
            # 2. 发现设备
            if not await self.demo_device_discovery():
                logger.warning("⚠️ 没有发现设备，跳过设备相关演示")
                await self.demo_homes_and_scenes()
                await self.demo_disconnect()
                return
            
            # 3. 选择第一个设备进行演示
            device_index = 0
            logger.info(f"\n🎯 使用设备 '{self.devices[device_index].name}' 进行演示")
            
            # 4. 获取设备属性
            await self.demo_device_properties(device_index)
            
            # 5. 获取设备动作
            await self.demo_device_actions(device_index)
            
            # 6. 属性操作演示
            await self.demo_property_operations(device_index)
            
            # 7. 获取设备状态
            await self.demo_device_status(device_index)
            
            # 8. 刷新所有设备状态
            await self.demo_refresh_all_status()
            
            # 9. 获取家庭和场景信息
            await self.demo_homes_and_scenes()
            
            # 10. 断开连接
            await self.demo_disconnect()
            
            logger.info("\n🎉 演示完成！")
            logger.info("=" * 50)
        
        except KeyboardInterrupt:
            logger.info("\n⏹️ 用户中断演示")
            await self.demo_disconnect()
        except Exception as e:
            logger.error(f"❌ 演示过程中发生错误: {e}")
            await self.demo_disconnect()

async def main():
    """主函数"""
    demo = MijiaAdapterDemo()
    await demo.run_full_demo()

if __name__ == "__main__":
    # 运行演示
    asyncio.run(main())