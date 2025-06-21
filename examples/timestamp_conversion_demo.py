#!/usr/bin/env python3
"""
Demonstration of automatic timestamp conversion in the NinjaRMM Python client.

This script shows how the library can automatically convert epoch timestamps
to human-readable ISO datetime format.
"""

import os
from ninjapy import NinjaRMMClient

def demo_timestamp_conversion():
    """Demonstrate timestamp conversion feature."""
    print("🕒 NinjaRMM Timestamp Conversion Demo")
    print("=" * 50)
    
    # Check for required environment variables
    required_vars = ["NINJA_TOKEN_URL", "NINJA_CLIENT_ID", "NINJA_CLIENT_SECRET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables before running the demo.")
        return
    
    print("✅ Environment variables found, starting demos...\n")
    
    # Demo 1: Client with timestamp conversion enabled (default)
    print("📋 Demo 1: Timestamp conversion ENABLED (default)")
    print("-" * 40)
    
    client_with_conversion = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control",
        convert_timestamps=True  # This is the default
    )
    
    try:
        # Get some devices
        devices = client_with_conversion.get_devices(page_size=3)
        
        if devices:
            print("✨ Sample device with converted timestamps:")
            device = devices[0]
            print(f"   Device ID: {device.get('id')}")
            print(f"   Display Name: {device.get('displayName', 'N/A')}")
            print(f"   Created: {device.get('created', 'N/A')}")
            print(f"   Last Contact: {device.get('lastContact', 'N/A')}")
            print(f"   Last Update: {device.get('lastUpdate', 'N/A')}")
            print()
            print("   📝 Notice: Timestamps are in ISO format (YYYY-MM-DDTHH:MM:SS.UUUUUUZ)")
        else:
            print("   No devices found")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Demo 2: Client with timestamp conversion disabled
    print("📋 Demo 2: Timestamp conversion DISABLED")
    print("-" * 40)
    
    client_without_conversion = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control",
        convert_timestamps=False
    )
    
    try:
        # Get the same devices
        devices = client_without_conversion.get_devices(page_size=3)
        
        if devices:
            print("🔢 Sample device with raw epoch timestamps:")
            device = devices[0]
            print(f"   Device ID: {device.get('id')}")
            print(f"   Display Name: {device.get('displayName', 'N/A')}")
            print(f"   Created: {device.get('created', 'N/A')}")
            print(f"   Last Contact: {device.get('lastContact', 'N/A')}")
            print(f"   Last Update: {device.get('lastUpdate', 'N/A')}")
            print()
            print("   📝 Notice: Timestamps are in epoch format (seconds since 1970-01-01)")
        else:
            print("   No devices found")
    
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Demo 3: Dynamically changing timestamp conversion
    print("📋 Demo 3: Dynamic timestamp conversion control")
    print("-" * 40)
    
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        print(f"   Initial setting: {client.get_timestamp_conversion_status()}")
        
        # Disable timestamp conversion
        client.set_timestamp_conversion(False)
        print(f"   After disabling: {client.get_timestamp_conversion_status()}")
        
        # Enable it again
        client.set_timestamp_conversion(True)
        print(f"   After re-enabling: {client.get_timestamp_conversion_status()}")
        
        print("   ✅ Dynamic control works!")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print()
    
    # Demo 4: Show conversion in different data types
    print("📋 Demo 4: Timestamp conversion in different data structures")
    print("-" * 40)
    
    try:
        # Get activities (nested data with timestamps)
        if devices:
            device_id = devices[0]['id']
            activities = client_with_conversion.get_device_activities(
                device_id=device_id, 
                page_size=2
            )
            
            if activities and 'results' in activities:
                print("📅 Sample activity with converted timestamps:")
                if activities['results']:
                    activity = activities['results'][0]
                    print(f"   Activity: {activity}")
                    print("   📝 Notice: All timestamp fields in nested structures are converted")
                else:
                    print("   No activities found for this device")
            else:
                print("   No activities data structure found")
        
        # Get organizations (list data with timestamps)
        orgs = client_with_conversion.get_organizations(page_size=2)
        if orgs:
            print("\n🏢 Organizations also have timestamp conversion:")
            org = orgs[0]
            print(f"   Organization: {org.get('name', 'N/A')}")
            # Note: Organizations might not have timestamp fields like devices
            for key, value in org.items():
                if any(ts_field in key.lower() for ts_field in ['time', 'date', 'created', 'updated']):
                    print(f"   {key}: {value}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Timestamp Conversion Demo Complete!")
    print("\n📚 Key Features:")
    print("• 🕒 Automatic conversion of epoch timestamps to ISO format")  
    print("• ⚙️  Configurable on client initialization")
    print("• 🔄 Can be toggled dynamically during runtime")
    print("• 🌲 Works with nested data structures (lists, dicts)")
    print("• 🎯 Recognizes common timestamp field names")
    print("• 📏 Preserves non-timestamp data unchanged")
    print("• 🔒 Safe handling of invalid timestamps")
    
    print("\n💡 Timestamp Format Examples:")
    print("   Epoch:     1728487941.725760000")
    print("   ISO:       2024-10-09T14:52:21.725760Z")
    print("   Epoch:     1640995200")
    print("   ISO:       2022-01-01T00:00:00Z")

def demo_manual_conversion():
    """Demonstrate manual timestamp conversion utilities."""
    print("\n🔧 Manual Timestamp Conversion Utilities")
    print("=" * 50)
    
    from ninjapy.utils import convert_epoch_to_iso, is_timestamp_field, is_epoch_timestamp
    
    # Example timestamps
    timestamps = [
        1728487941.725760000,  # With microseconds
        1640995200,            # Without microseconds
        "1728487941.725760",   # String format
    ]
    
    print("📝 Converting individual timestamps:")
    for ts in timestamps:
        iso_time = convert_epoch_to_iso(ts)
        print(f"   {ts} → {iso_time}")
    
    print("\n🔍 Field name detection:")
    field_names = ['created', 'lastContact', 'name', 'installDate', 'description', 'updatedAt']
    for field in field_names:
        is_ts = is_timestamp_field(field)
        print(f"   '{field}' → {'✅ Timestamp field' if is_ts else '❌ Regular field'}")
    
    print("\n🧮 Value detection:")
    values = [1728487941.725760, 42, "not_a_timestamp", -1, 9999999999999]
    for value in values:
        is_ts = is_epoch_timestamp(value)
        print(f"   {value} → {'✅ Looks like timestamp' if is_ts else '❌ Not a timestamp'}")

if __name__ == "__main__":
    demo_timestamp_conversion()
    demo_manual_conversion() 