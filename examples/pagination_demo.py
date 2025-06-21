#!/usr/bin/env python3
"""
Demonstration of automatic pagination features in the NinjaRMM Python client.

This script shows how to use the new auto-pagination methods to easily
retrieve all records from endpoints that support pagination.
"""

import os
import time
from ninjapy import NinjaRMMClient

def demo_basic_pagination():
    """Demonstrate basic 'after' parameter pagination."""
    print("🔄 Demo: Basic Pagination (Organizations)")
    print("=" * 50)
    
    # Initialize client 
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        # Old way: Manual pagination
        print("📋 Old way - Manual pagination:")
        page_size = 10
        after = None
        all_orgs_manual = []
        
        while True:
            orgs = client.get_organizations(page_size=page_size, after=after)
            if not orgs:
                break
            all_orgs_manual.extend(orgs)
            if len(orgs) < page_size:
                break
            after = orgs[-1]['id']
        
        print(f"   Retrieved {len(all_orgs_manual)} organizations manually")
        
        # New way: Automatic pagination
        print("\n✨ New way - Automatic pagination:")
        all_orgs_auto = client.get_all_organizations(page_size=10)
        print(f"   Retrieved {len(all_orgs_auto)} organizations automatically")
        
        # Verify they're the same
        print(f"   ✅ Results match: {len(all_orgs_manual) == len(all_orgs_auto)}")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def demo_iterator_pagination():
    """Demonstrate memory-efficient iterator pagination."""
    print("\n🔄 Demo: Memory-Efficient Iterator Pagination")
    print("=" * 50)
    
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        print("📋 Processing devices one at a time (memory efficient):")
        
        # Process devices one at a time without loading all into memory
        device_count = 0
        for device in client.iter_all_devices(page_size=50):
            device_count += 1
            print(f"   Processing device {device_count}: {device.get('displayName', 'Unknown')}")
            
            # Process only first 5 for demo
            if device_count >= 5:
                print("   ... (stopping demo after 5 devices)")
                break
        
        print(f"   ✅ Processed {device_count} devices efficiently")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def demo_cursor_pagination():
    """Demonstrate cursor-based pagination for query endpoints."""
    print("\n🔄 Demo: Cursor-Based Pagination (Query Endpoints)")
    print("=" * 50)
    
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        # Search for devices (cursor-based pagination)
        print("📋 Searching all devices:")
        search_results = client.search_all_devices("Windows", page_size=25)
        print(f"   Found {len(search_results)} Windows devices")
        
        # Query all Windows services (cursor-based pagination)
        print("\n📋 Querying all Windows services:")
        services = client.query_all_windows_services(
            device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
            page_size=100
        )
        print(f"   Found {len(services)} Windows services")
        
        # Get all custom fields (cursor-based pagination)
        print("\n📋 Getting all custom fields:")
        custom_fields = client.query_all_custom_fields(page_size=50)
        print(f"   Found {len(custom_fields)} custom field entries")
        
        print("   ✅ All cursor-based queries completed successfully")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def demo_filtering_with_pagination():
    """Demonstrate pagination with filters."""
    print("\n🔄 Demo: Pagination with Filters")
    print("=" * 50)
    
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        # Get all devices for a specific organization
        print("📋 Getting devices for specific organization:")
        org_devices = client.get_all_devices(
            org_filter="organization-1",  # Replace with actual org filter
            page_size=20
        )
        print(f"   Found {len(org_devices)} devices in organization")
        
        # Query Windows services with filters
        print("\n📋 Querying running Windows services on workstations:")
        running_services = client.query_all_windows_services(
            device_filter="deviceClass eq 'WINDOWS_WORKSTATION'",
            state="running",
            page_size=100
        )
        print(f"   Found {len(running_services)} running services")
        
        print("   ✅ Filtered pagination completed successfully")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def demo_performance_comparison():
    """Demonstrate performance benefits of pagination."""
    print("\n🔄 Demo: Performance Comparison")
    print("=" * 50)
    
    client = NinjaRMMClient(
        token_url=os.getenv("NINJA_TOKEN_URL"),
        client_id=os.getenv("NINJA_CLIENT_ID"),
        client_secret=os.getenv("NINJA_CLIENT_SECRET"),
        scope="monitoring management control"
    )
    
    try:
        # Small page size (many requests)
        print("📋 Testing with small page size (page_size=5):")
        start_time = time.time()
        small_page_orgs = client.get_all_organizations(page_size=5)
        small_page_time = time.time() - start_time
        print(f"   Retrieved {len(small_page_orgs)} orgs in {small_page_time:.2f}s")
        
        # Large page size (fewer requests)
        print("\n📋 Testing with large page size (page_size=100):")
        start_time = time.time()
        large_page_orgs = client.get_all_organizations(page_size=100)
        large_page_time = time.time() - start_time
        print(f"   Retrieved {len(large_page_orgs)} orgs in {large_page_time:.2f}s")
        
        # Performance analysis
        if large_page_time > 0:
            speedup = small_page_time / large_page_time
            print(f"\n   📊 Performance: {speedup:.1f}x faster with larger page size")
        
        print("   ✅ Performance comparison completed")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")

def main():
    """Run all pagination demos."""
    print("🚀 NinjaRMM Pagination Features Demo")
    print("=" * 50)
    
    # Check for required environment variables
    required_vars = ["NINJA_TOKEN_URL", "NINJA_CLIENT_ID", "NINJA_CLIENT_SECRET"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("❌ Missing required environment variables:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\nPlease set these variables before running the demo.")
        print("You can use the .env.example file as a template.")
        return
    
    print("✅ Environment variables found, starting demos...\n")
    
    try:
        # Run all demos
        demo_basic_pagination()
        demo_iterator_pagination()
        demo_cursor_pagination()
        demo_filtering_with_pagination()
        demo_performance_comparison()
        
        print("\n" + "=" * 50)
        print("🎉 All pagination demos completed successfully!")
        print("\nKey Benefits:")
        print("• 📦 Get ALL records with a single method call")
        print("• 🧠 Memory-efficient iterators for large datasets")
        print("• 🔄 Automatic handling of both pagination types")
        print("• 🎯 Works with filters and search parameters")
        print("• ⚡ Optimizable with page_size parameter")
        
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")

if __name__ == "__main__":
    main() 