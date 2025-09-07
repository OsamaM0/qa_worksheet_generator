#!/usr/bin/env python3
"""
Test script to verify Playwright functionality in Docker environment
"""

import asyncio
import logging
import sys
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_playwright():
    """Test basic Playwright functionality"""
    print("=== Testing Playwright in Docker Environment ===")
    
    playwright = None
    browser = None
    
    try:
        # Initialize Playwright
        print("1. Starting Playwright...")
        playwright = await async_playwright().start()
        print("✓ Playwright started successfully")
        
        # Launch browser
        print("2. Launching Chromium browser...")
        browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--disable-gpu',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-default-apps',
                '--disable-web-security',
                '--disable-features=TranslateUI',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding'
            ]
        )
        print("✓ Browser launched successfully")
        
        # Create page and test basic functionality
        print("3. Creating new page...")
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1200, "height": 800})
        print("✓ Page created successfully")
        
        # Test HTML content rendering
        print("4. Testing HTML content rendering...")
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Playwright Test</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                .test-div { background: lightblue; padding: 20px; border-radius: 10px; }
            </style>
        </head>
        <body>
            <div class="test-div">
                <h1>Playwright Test Page</h1>
                <p>This is a test to verify Playwright is working correctly in Docker.</p>
                <script>window.testComplete = true;</script>
            </div>
        </body>
        </html>
        """
        
        await page.set_content(test_html, wait_until='domcontentloaded')
        await page.wait_for_function("window.testComplete === true", timeout=30000)
        print("✓ HTML content rendered successfully")
        
        # Test screenshot capability
        print("5. Testing screenshot capability...")
        screenshot_bytes = await page.screenshot(type='png', full_page=True)
        print(f"✓ Screenshot taken successfully ({len(screenshot_bytes)} bytes)")
        
        # Test mindmap-like content
        print("6. Testing mindmap-like content...")
        mindmap_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Mindmap Test</title>
            <script src="https://unpkg.com/gojs@2.3.11/release/go.js"></script>
            <style>
                #myDiagramDiv { width: 800px; height: 600px; border: 1px solid black; }
            </style>
        </head>
        <body>
            <div id="myDiagramDiv"></div>
            <script>
                var $ = go.GraphObject.make;
                var diagram = $(go.Diagram, "myDiagramDiv");
                
                diagram.nodeTemplate =
                    $(go.Node, "Auto",
                        $(go.Shape, "RoundedRectangle", { fill: "lightblue" }),
                        $(go.TextBlock, { margin: 10 }, new go.Binding("text", "text"))
                    );
                
                diagram.model = new go.TreeModel([
                    { key: 0, text: "Test Root" },
                    { key: 1, parent: 0, text: "Child 1" },
                    { key: 2, parent: 0, text: "Child 2" }
                ]);
                
                // Signal that diagram is ready
                setTimeout(() => { window.diagramReady = true; }, 1000);
            </script>
        </body>
        </html>
        """
        
        await page.set_content(mindmap_html, wait_until='domcontentloaded')
        await page.wait_for_function("window.diagramReady === true", timeout=30000)
        
        # Take screenshot of the diagram
        diagram_element = await page.query_selector('#myDiagramDiv')
        if diagram_element:
            mindmap_screenshot = await diagram_element.screenshot(type='png')
            print(f"✓ Mindmap screenshot taken successfully ({len(mindmap_screenshot)} bytes)")
        else:
            print("⚠ Diagram element not found, but page loaded successfully")
        
        print("\n=== All tests passed! Playwright is working correctly ===")
        return True
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        logger.error(f"Playwright test error: {e}")
        return False
        
    finally:
        # Cleanup
        try:
            if browser:
                await browser.close()
                print("✓ Browser closed")
            if playwright:
                await playwright.stop()
                print("✓ Playwright stopped")
        except Exception as cleanup_error:
            print(f"⚠ Cleanup warning: {cleanup_error}")

def main():
    """Main test function"""
    try:
        result = asyncio.run(test_playwright())
        if result:
            print("\n🎉 Playwright Docker test completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Playwright Docker test failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
