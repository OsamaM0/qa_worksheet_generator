"""
Mindmap Image Generation Service
Generates PNG images from mindmap JSON data and uploads to S3
"""

import os
import json
import logging
import tempfile
import asyncio
import io
import sys
import platform
from playwright.async_api import async_playwright
from typing import Dict, Any, Optional
from s3_service import get_s3_service
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

class MindMapImageGenerator:
    def __init__(self):
        """Initialize mindmap image generator"""
        self.s3_service = get_s3_service()
        
    async def generate_image(self, mind_map_json: Dict[str, Any], 
                           width: int = 1200, height: int = 800, 
                           format: str = 'png') -> bytes:
        """Generate PNG image from mind map JSON with fresh browser instance"""
        playwright = None
        browser = None
        page = None
        
        try:
            logger.debug("Starting fresh Playwright browser...")
            playwright = await async_playwright().start()
            
            # Windows-compatible browser args - more conservative approach
            browser_args = [
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
            
            browser = await playwright.chromium.launch(
                headless=True,
                args=browser_args
            )
            logger.debug("Browser launched successfully")
            
            # Create the HTML content with the mind map
            html_content = self._create_html_content(mind_map_json, width, height)
            
            # Create a new page
            logger.debug("Creating new browser page...")
            page = await browser.new_page()
            await page.set_viewport_size({"width": width, "height": height})
            
            # Set the HTML content
            logger.debug("Setting HTML content...")
            logger.debug(f"Mindmap data has {len(mind_map_json.get('nodeDataArray', []))} nodes")
            
            try:
                await page.set_content(html_content, wait_until='domcontentloaded', timeout=45000)
                logger.debug("HTML content set successfully")
            except Exception as content_error:
                logger.warning(f"Failed to set content normally, trying alternative: {content_error}")
                # Alternative approach - navigate to data URL
                import base64
                html_b64 = base64.b64encode(html_content.encode('utf-8')).decode('ascii')
                await page.goto(f"data:text/html;base64,{html_b64}", wait_until='domcontentloaded', timeout=45000)
                logger.debug("HTML content set via data URL")
            
            # Wait for the diagram to be rendered with better error handling
            logger.debug("Waiting for diagram to be ready...")
            try:
                await page.wait_for_function("window.diagramReady === true", timeout=45000)
            except Exception as wait_error:
                logger.warning(f"Diagram ready wait failed, proceeding anyway: {wait_error}")
                # Give it some extra time
                await asyncio.sleep(3)
            
            # Take screenshot of the diagram div
            logger.debug("Taking screenshot...")
            diagram_element = await page.query_selector('#myDiagramDiv')
            if not diagram_element:
                logger.warning("Diagram element not found, taking full page screenshot")
                screenshot_bytes = await page.screenshot(type=format, full_page=True)
            else:
                screenshot_bytes = await diagram_element.screenshot(type=format)
            logger.debug(f"Screenshot taken, size: {len(screenshot_bytes)} bytes")
            
            # Add watermark to the image
            screenshot_bytes = self._add_watermark_to_image(screenshot_bytes)
            
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise
        finally:
            # Always cleanup everything with proper error handling
            cleanup_errors = []
            try:
                if page and not page.is_closed():
                    await page.close()
            except Exception as e:
                cleanup_errors.append(f"Page close: {e}")
            
            try:
                if browser:
                    await browser.close()
            except Exception as e:
                cleanup_errors.append(f"Browser close: {e}")
            
            try:
                if playwright:
                    await playwright.stop()
            except Exception as e:
                cleanup_errors.append(f"Playwright stop: {e}")
            
            if cleanup_errors:
                logger.warning(f"Cleanup warnings: {'; '.join(cleanup_errors)}")
            else:
                logger.debug("Browser resources cleaned up successfully")
    
    def _add_watermark_to_image(self, image_bytes: bytes) -> bytes:
        """Add watermark to the generated PNG image"""
        try:
            from PIL import Image, ImageDraw, ImageFont
            import io
            
            # Open the image from bytes
            image = Image.open(io.BytesIO(image_bytes))
            
            # Create a drawing context
            draw = ImageDraw.Draw(image)
            
            # Watermark box dimensions
            box_width = 180
            box_height = 70
            box_x = 10  # 10px from left edge
            box_y = 10  # 10px from top edge
            
            # Draw white box with border
            box_coords = [box_x, box_y, box_x + box_width, box_y + box_height]
            draw.rectangle(box_coords, fill='white', outline='white', width=1)
            
            # Text content
            text_line1 = "Tahder +"
            text_line2 = "Your Smart Learning Platform in Saudi Arabia"
            text_line3 = "© 2022-2025 All rights reserved"
            
            # Try to load a font (fallback to default if not available)
            try:
                font_title = ImageFont.truetype("arial.ttf", 12)
                font_small = ImageFont.truetype("arial.ttf", 9)
            except:
                try:
                    font_title = ImageFont.load_default()
                    font_small = ImageFont.load_default()
                except:
                    # If all else fails, use the draw methods without font
                    font_title = None
                    font_small = None
            
            # Calculate text positions
            text_color = 'black'
            line_spacing = 2
            
            # Position text in the box
            text_x = box_x + 5  # 5px padding from left edge of box
            text_y = box_y + 5  # 5px padding from top edge of box
            
            # Draw text lines
            if font_title and font_small:
                # Draw "Tahder +" in slightly larger font
                draw.text((text_x, text_y), text_line1, fill=text_color, font=font_title)
                
                # Get text height for positioning next lines
                bbox = draw.textbbox((0, 0), text_line1, font=font_title)
                line1_height = bbox[3] - bbox[1]
                
                # Draw "All rights reserved"
                text_y2 = text_y + line1_height + line_spacing
                draw.text((text_x, text_y2), text_line2, fill=text_color, font=font_small)
                
                # Get text height for positioning last line
                bbox = draw.textbbox((0, 0), text_line2, font=font_small)
                line2_height = bbox[3] - bbox[1]
                
                # Draw "from 2022 - 2025"
                text_y3 = text_y2 + line2_height + line_spacing
                draw.text((text_x, text_y3), text_line3, fill=text_color, font=font_small)
            else:
                # Fallback if fonts are not available
                draw.text((text_x, text_y), text_line1, fill=text_color)
                draw.text((text_x, text_y + 15), text_line2, fill=text_color)
                draw.text((text_x, text_y + 30), text_line3, fill=text_color)
            
            # Convert back to bytes
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='PNG')
            return output_buffer.getvalue()
            
        except Exception as e:
            logger.warning(f"Failed to add watermark to image: {e}")
            # Return original image if watermarking fails
            return image_bytes
    
    def _create_html_content(self, mind_map_json: Dict[str, Any], width: int, height: int) -> str:
        """Create HTML content with GoJS mind map - exact copy from main_image.py"""
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mind Map Image Generator</title>
    <script src="https://unpkg.com/gojs@3.0.7/release/go.js"></script>
    <style>
        body {{
            margin: 0;
            padding: 0;
            font-family: sans-serif;
        }}
        #myDiagramDiv {{
            width: {width}px;
            height: {height}px;
            background-color: white;
        }}
    </style>
</head>
<body>
    <div id="myDiagramDiv"></div>
    
    <script>
        let myDiagram;
        window.diagramReady = false;
        
        function init() {{
            const $ = go.GraphObject.make;

            myDiagram = new go.Diagram('myDiagramDiv', {{
                'commandHandler.copiesTree': true,
                'commandHandler.copiesParentKey': true,
                'commandHandler.deletesTree': true,
                'draggingTool.dragsTree': true,
                'undoManager.isEnabled': false,
                initialAutoScale: go.AutoScale.Uniform
            }});

            // Node template - same as original
            myDiagram.nodeTemplate = $(go.Node,
                'Vertical',
                {{ selectionObjectName: 'TEXT' }},
                $(go.Panel,
                    'Auto',
                    $(go.Shape,
                        'RoundedRectangle',
                        {{
                            fill: 'white',
                            stroke: 'black',
                            strokeWidth: 2,
                            portId: '',
                            fromSpot: go.Spot.AllSides,
                            toSpot: go.Spot.AllSides,
                        }},
                        new go.Binding('fill', 'brush'),
                        new go.Binding('stroke', 'brush')
                    ),
                    $(go.TextBlock,
                        {{
                            name: 'TEXT',
                            minSize: new go.Size(30, 15),
                            editable: false,
                            margin: 8,
                            font: 'bold 12px sans-serif',
                            stroke: 'white',
                            textAlign: 'center'
                        }},
                        new go.Binding('text', 'text'),
                        new go.Binding('scale', 'scale'),
                        new go.Binding('font', 'font'),
                        new go.Binding('stroke', 'brush', (brush) => {{
                            const darkColors = ['#9C27B0', '#F44336', '#4CAF50', '#2196F3'];
                            return darkColors.includes(brush) ? 'white' : 'black';
                        }})
                    )
                ),
                new go.Binding('location', 'loc', go.Point.parse),
                new go.Binding('locationSpot', 'dir', (d) => spotConverter(d, false))
            );

            // Link template - same as original
            myDiagram.linkTemplate = $(go.Link,
                {{
                    curve: go.Curve.Bezier,
                    fromShortLength: -2,
                    toShortLength: -2,
                    selectable: false,
                }},
                $(go.Shape,
                    {{ 
                        strokeWidth: 4,
                        stroke: 'gray'
                    }},
                    new go.Binding('stroke', 'toNode', (n) => {{
                        if (n.data.brush) return n.data.brush;
                        return 'gray';
                    }}).ofObject()
                )
            );

            // Load the mind map data
            const mindMapData = {json.dumps(mind_map_json)};
            myDiagram.model = go.Model.fromJson(mindMapData);
            
            // Layout the diagram
            layoutAll();
            
            // Mark as ready after a short delay to ensure rendering is complete
            setTimeout(() => {{
                window.diagramReady = true;
                console.log('Diagram is ready');
            }}, 1000);
        }}

        function spotConverter(dir, from) {{
            if (dir === 'left') {{
                return from ? go.Spot.Left : go.Spot.Right;
            }} else {{
                return from ? go.Spot.Right : go.Spot.Left;
            }}
        }}

        function layoutAngle(parts, angle) {{
            var layout = new go.TreeLayout({{
                angle: angle,
                arrangement: go.TreeArrangement.FixedRoots,
                nodeSpacing: 5,
                layerSpacing: 20,
                setsPortSpot: false,
                setsChildPortSpot: false,
            }});
            layout.doLayout(parts);
        }}

        function layoutAll() {{
            var root = myDiagram.findTreeRoots().first();
            if (root === null) return;
            myDiagram.startTransaction('Layout');
            var rightward = new go.Set();
            var leftward = new go.Set();
            root.findLinksConnected().each((link) => {{
                var child = link.toNode;
                if (child.data.dir === 'left') {{
                    leftward.add(root);
                    leftward.add(link);
                    leftward.addAll(child.findTreeParts());
                }} else {{
                    rightward.add(root);
                    rightward.add(link);
                    rightward.addAll(child.findTreeParts());
                }}
            }});
            layoutAngle(rightward, 0);
            layoutAngle(leftward, 180);
            myDiagram.commitTransaction('Layout');
        }}

        // Initialize when DOM is loaded
        document.addEventListener('DOMContentLoaded', init);
    </script>
</body>
</html>
        """

    def run_async_safely(self, coro):
        """Safely run async coroutine in sync context with Windows compatibility"""
        import threading
        import concurrent.futures
        import platform
        import sys
        
        def run_in_thread():
            """Run coroutine in a separate thread with its own event loop"""
            # Set event loop policy for Windows compatibility
            if platform.system() == "Windows":
                # Use ProactorEventLoop for Windows to handle subprocess better
                if sys.version_info >= (3, 8):
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                else:
                    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
            
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        
        # Always run in a separate thread to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result(timeout=120)  # Increased timeout for Windows

    def generate_mindmap_image_and_upload(self, mindmap_data: Dict[str, Any], 
                                        title: str = "mindmap",
                                        width: int = 1200, height: int = 800) -> Dict[str, Any]:
        """
        Generate mindmap image and upload to S3
        
        Args:
            mindmap_data: The mindmap JSON data containing nodeDataArray
            title: Title for file naming
            width: Image width in pixels
            height: Image height in pixels
        
        Returns:
            Dictionary with upload results and public URL
        """
        try:
            logger.info(f"Generating mindmap image for: {title}")
            
            # Try to generate image with Playwright (with more retries)
            playwright_success = False
            last_playwright_error = None
            
            for attempt in range(3):  # Try up to 3 times
                try:
                    logger.info(f"Playwright attempt {attempt + 1}/3")
                    image_bytes = self.run_async_safely(
                        self.generate_image(mindmap_data, width, height, 'png')
                    )
                    playwright_success = True
                    logger.info("Playwright image generation successful")
                    break
                except Exception as playwright_error:
                    last_playwright_error = playwright_error
                    logger.warning(f"Playwright attempt {attempt + 1} failed: {playwright_error}")
                    if attempt < 2:  # Don't sleep on the last attempt
                        import time
                        time.sleep(2)  # Wait 2 seconds between attempts
            
            if not playwright_success:
                logger.error(f"All Playwright attempts failed. Last error: {last_playwright_error}")
                # Only use fallback as last resort
                logger.info("Using fallback image generation method...")
                image_bytes = self._generate_image_fallback(mindmap_data, width, height)
            
            # Create temporary file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            
            # Clean title for filename
            import re
            clean_title = re.sub(r'[<>:"/\\|?*]', '_', title)
            filename = f"mindmap_{clean_title}_{timestamp}_{unique_id}.png"
            
            temp_file_path = os.path.join(tempfile.gettempdir(), filename)
            
            # Save image to temporary file
            with open(temp_file_path, 'wb') as f:
                f.write(image_bytes)
            
            logger.info(f"Image saved to temporary file: {temp_file_path}")
            
            # Upload to S3
            s3_key = f"mindmaps/{filename}"
            
            # Convert non-ASCII characters in metadata to ASCII-safe format
            import base64
            title_ascii = base64.b64encode(title.encode('utf-8')).decode('ascii') if any(ord(c) > 127 for c in title) else title
            
            upload_result = self.s3_service.upload_file(
                local_file_path=temp_file_path,
                s3_key=s3_key,
                content_type='image/png',
                metadata={
                    'title_base64': title_ascii,
                    'width': str(width),
                    'height': str(height),
                    'type': 'mindmap',
                    'original_title': title[:50] if len(title) <= 50 and all(ord(c) < 128 for c in title) else 'mindmap'
                }
            )
            
            # Clean up temporary file
            try:
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as cleanup_error:
                logger.warning(f"Could not clean up temporary file: {cleanup_error}")
            
            if upload_result["status"] == "success":
                logger.info(f"Mindmap image uploaded successfully: {upload_result['public_url']}")
                
                return {
                    "status": "success",
                    "message": "Mindmap image generated and uploaded successfully",
                    "public_url": upload_result["public_url"],
                    "s3_key": upload_result["s3_key"],
                    "file_size": upload_result["file_size"],
                    "image_info": {
                        "width": width,
                        "height": height,
                        "format": "png"
                    },
                    "upload_time": upload_result["upload_time"]
                }
            else:
                logger.error(f"S3 upload failed: {upload_result}")
                return {
                    "status": "error",
                    "message": f"Failed to upload image to S3: {upload_result.get('message', 'Unknown error')}",
                    "upload_error": upload_result
                }
                
        except Exception as e:
            logger.error(f"Error generating mindmap image: {e}")
            return {
                "status": "error",
                "message": f"Failed to generate mindmap image: {str(e)}"
            }
    
    def _generate_image_fallback(self, mindmap_data: Dict[str, Any], 
                               width: int, height: int) -> bytes:
        """
        Fallback method to generate a simple mindmap image using PIL when Playwright fails
        """
        try:
            from PIL import Image, ImageDraw, ImageFont
            import math
            
            logger.info("Using PIL fallback for mindmap image generation")
            
            # Create image
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            
            # Try to load a font (fallback to default if not available)
            try:
                font = ImageFont.truetype("arial.ttf", 16)
                font_large = ImageFont.truetype("arial.ttf", 20)
            except:
                font = ImageFont.load_default()
                font_large = font
            
            # Extract nodes
            nodes = mindmap_data.get("nodeDataArray", [])
            if not nodes:
                # Create a simple "No Data" image
                draw.text((width//2 - 50, height//2), "No Mindmap Data", fill='black', font=font)
                
                # Convert to bytes
                img_buffer = io.BytesIO()
                img.save(img_buffer, format='PNG')
                return img_buffer.getvalue()
            
            # Simple layout algorithm for fallback
            center_x, center_y = width // 2, height // 2
            positions = {}
            
            # Find root node (no parent)
            root_node = None
            for node in nodes:
                if node.get('parent') is None or node.get('parent') == 0:
                    root_node = node
                    break
            
            if root_node:
                # Position root at center
                positions[root_node['key']] = (center_x, center_y)
                
                # Position child nodes in a circle around root
                child_nodes = [n for n in nodes if n.get('parent') == root_node['key']]
                if child_nodes:
                    angle_step = 2 * math.pi / len(child_nodes)
                    radius = min(width, height) // 4
                    
                    for i, child in enumerate(child_nodes):
                        angle = i * angle_step
                        x = center_x + int(radius * math.cos(angle))
                        y = center_y + int(radius * math.sin(angle))
                        positions[child['key']] = (x, y)
                        
                        # Position grandchildren
                        grandchildren = [n for n in nodes if n.get('parent') == child['key']]
                        if grandchildren:
                            sub_radius = radius // 2
                            sub_angle_step = angle_step / (len(grandchildren) + 1)
                            for j, grandchild in enumerate(grandchildren):
                                sub_angle = angle + (j + 1) * sub_angle_step - angle_step/2
                                gx = x + int(sub_radius * math.cos(sub_angle))
                                gy = y + int(sub_radius * math.sin(sub_angle))
                                positions[grandchild['key']] = (gx, gy)
            
            # Draw connections first
            for node in nodes:
                if node.get('parent') and node['key'] in positions:
                    parent_key = node['parent']
                    if parent_key in positions:
                        start_pos = positions[parent_key]
                        end_pos = positions[node['key']]
                        draw.line([start_pos, end_pos], fill='gray', width=2)
            
            # Draw nodes
            for node in nodes:
                if node['key'] in positions:
                    x, y = positions[node['key']]
                    text = node.get('text', f"Node {node['key']}")
                    
                    # Get text size
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]
                    
                    # Draw node background
                    padding = 10
                    rect = [
                        x - text_width//2 - padding,
                        y - text_height//2 - padding,
                        x + text_width//2 + padding,
                        y + text_height//2 + padding
                    ]
                    
                    # Use node color if available
                    fill_color = node.get('brush', '#E0E0E0')
                    if fill_color.startswith('#'):
                        try:
                            draw.rectangle(rect, fill=fill_color, outline='black')
                        except:
                            draw.rectangle(rect, fill='lightgray', outline='black')
                    else:
                        draw.rectangle(rect, fill='lightgray', outline='black')
                    
                    # Draw text
                    text_color = 'black'
                    if fill_color in ['#9C27B0', '#F44336', '#4CAF50', '#2196F3']:
                        text_color = 'white'
                    
                    draw.text((x - text_width//2, y - text_height//2), text, 
                             fill=text_color, font=font)
            
            # Convert to bytes
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            image_bytes = img_buffer.getvalue()
            
            # Add watermark to the fallback image
            return self._add_watermark_to_image(image_bytes)
            
        except Exception as e:
            logger.error(f"Fallback image generation failed: {e}")
            # Create a simple error image
            img = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(img)
            draw.text((50, height//2), f"Error generating mindmap: {str(e)[:50]}...", 
                     fill='red')
            
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            image_bytes = img_buffer.getvalue()
            
            # Add watermark even to error images
            return self._add_watermark_to_image(image_bytes)


class MindMapService:
    """Service for handling mindmap operations"""
    
    def __init__(self):
        self.image_generator = MindMapImageGenerator()
    
    def create_sample_mindmap_data(self) -> Dict[str, Any]:
        """Create sample mindmap data for testing - using the same complex structure as main_image.py"""
        return {
            "class": "go.TreeModel",
            "nodeDataArray": [
                {
                    "key": 0,
                    "text": "خريطة شاملة",
                    "loc": "0 0",
                    "brush": "gold"
                },
                {
                    "key": 1,
                    "parent": 0,
                    "text": "الاتجاه التجديدي في الدراسات الأدبية",
                    "dir": "right",
                    "brush": "skyblue"
                },
                {
                    "key": 2,
                    "parent": 1,
                    "text": "الاتجاه الاجتماعي",
                    "brush": "gold",
                    "dir": "left"
                },
                {
                    "key": 3,
                    "parent": 2,
                    "text": "تأثير المجتمع على الشعراء",
                    "brush": "gold",
                    "dir": "null"
                },
                {
                    "key": 4,
                    "parent": 2,
                    "text": "الاهتمام بالقضايا الاجتماعية",
                    "brush": "gold",
                    "dir": "null"
                },
                {
                    "key": 5,
                    "parent": 1,
                    "text": "الخصائص الشعرية",
                    "brush": "palevioletred",
                    "dir": "right"
                },
                {
                    "key": 6,
                    "parent": 5,
                    "text": "المزاوجة بين القوافي",
                    "brush": "palevioletred",
                    "dir": "null"
                },
                {
                    "key": 7,
                    "parent": 5,
                    "text": "اختيار البحور",
                    "brush": "palevioletred",
                    "dir": "null"
                },
                {
                    "key": 8,
                    "parent": 1,
                    "text": "مواضيع الشعر",
                    "brush": "darkseagreen",
                    "dir": "left"
                },
                {
                    "key": 9,
                    "parent": 8,
                    "text": "المناسبات",
                    "brush": "darkseagreen",
                    "dir": "null"
                },
                {
                    "key": 10,
                    "parent": 8,
                    "text": "الشعر الفردي",
                    "brush": "darkseagreen",
                    "dir": "null"
                },
                {
                    "key": 11,
                    "parent": 1,
                    "text": "المرحلة الأولى",
                    "brush": "skyblue",
                    "dir": "right"
                },
                {
                    "key": 12,
                    "parent": 11,
                    "text": "أساليب التجديد",
                    "brush": "skyblue",
                    "dir": "right"
                },
                {
                    "key": 13,
                    "parent": 12,
                    "text": "التجديد في الشكل",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 14,
                    "parent": 12,
                    "text": "التجديد في المضمون",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 15,
                    "parent": 11,
                    "text": "الشعراء المجددون",
                    "brush": "skyblue",
                    "dir": "right"
                },
                {
                    "key": 16,
                    "parent": 15,
                    "text": "عبدالسلام أبولو",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 17,
                    "parent": 15,
                    "text": "أحمد قنديل",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 18,
                    "parent": 15,
                    "text": "حسن عواد",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 19,
                    "parent": 15,
                    "text": "محمد حسن فقي",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 20,
                    "parent": 15,
                    "text": "أحمد عبد الجبار",
                    "brush": "skyblue",
                    "dir": "null"
                },
                {
                    "key": 21,
                    "parent": 0,
                    "text": "الشعر",
                    "dir": "left",
                    "brush": "skyblue"
                },
                {
                    "key": 22,
                    "parent": 21,
                    "text": "الوحدة المعنوية",
                    "brush": "gold",
                    "dir": "right"
                },
                {
                    "key": 23,
                    "parent": 21,
                    "text": "الشعر الاجتماعي",
                    "brush": "gold",
                    "dir": "left"
                },
                {
                    "key": 24,
                    "parent": 23,
                    "text": "الشعر الذاتي",
                    "brush": "plum",
                    "dir": "null"
                },
                {
                    "key": 25,
                    "parent": 23,
                    "text": "سعد البواردي",
                    "brush": "plum",
                    "dir": "null"
                }
            ]
        }
    
    def process_mindmap_from_db(self, document_uuid: str, 
                              width: int = 1200, height: int = 800) -> Dict[str, Any]:
        """
        Get mindmap data from database and generate image
        
        Args:
            document_uuid: Document UUID to find in mindmaps collection
            width: Image width in pixels
            height: Image height in pixels
        
        Returns:
            Dictionary with mindmap data and image URL
        """
        try:
            # Import here to avoid circular imports
            from app import create_mindmap_from_ai_db, MONGO_URI, DB_NAME
            
            # Get mindmap data from database
            mindmap_result = create_mindmap_from_ai_db(
                document_uuid=document_uuid,
                mongo_uri=MONGO_URI,
                db_name=DB_NAME,
                html_parsing=False,
                include_raw_meta=False
            )
            
            mindmap_data = mindmap_result.get("mindmap", {})
            title = mindmap_result.get("title", f"mindmap_{document_uuid}")
            
            if not mindmap_data:
                return {
                    "status": "error",
                    "message": "No mindmap data found in the document"
                }
            
            # Generate and upload image
            image_result = self.image_generator.generate_mindmap_image_and_upload(
                mindmap_data=mindmap_data,
                title=title,
                width=width,
                height=height
            )
            
            if image_result["status"] == "success":
                return {
                    "status": "success",
                    "message": "Mindmap processed and image generated successfully",
                    "document_uuid": document_uuid,
                    "title": title,
                    "mindmap_data": mindmap_data,
                    "image": image_result,
                    "meta": mindmap_result.get("meta", {})
                }
            else:
                return {
                    "status": "error",
                    "message": f"Failed to generate image: {image_result.get('message', 'Unknown error')}",
                    "document_uuid": document_uuid,
                    "mindmap_data": mindmap_data,
                    "image_error": image_result
                }
                
        except Exception as e:
            logger.error(f"Error processing mindmap from DB: {e}")
            return {
                "status": "error",
                "message": f"Failed to process mindmap: {str(e)}",
                "document_uuid": document_uuid
            }
    
    def generate_image_from_json(self, mindmap_json: Dict[str, Any],
                               title: str = "custom_mindmap",
                               width: int = 1200, height: int = 800) -> Dict[str, Any]:
        """
        Generate image from provided mindmap JSON data
        
        Args:
            mindmap_json: The mindmap JSON data
            title: Title for file naming
            width: Image width in pixels
            height: Image height in pixels
        
        Returns:
            Dictionary with image generation results
        """
        return self.image_generator.generate_mindmap_image_and_upload(
            mindmap_data=mindmap_json,
            title=title,
            width=width,
            height=height
        )


# Singleton instance
_mindmap_service = None

def get_mindmap_service() -> MindMapService:
    """Get singleton mindmap service instance"""
    global _mindmap_service
    if _mindmap_service is None:
        _mindmap_service = MindMapService()
    return _mindmap_service


if __name__ == "__main__":
    # Test the mindmap service
    try:
        service = MindMapService()
        
        # Test with sample data
        sample_data = service.create_sample_mindmap_data()
        result = service.generate_image_from_json(sample_data, "test_mindmap")
        
        print(f"Test result: {result}")
        
    except Exception as e:
        print(f"Mindmap Service Error: {e}")
