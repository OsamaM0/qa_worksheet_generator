from flask import Flask, request, jsonify, send_file
import os
import json
import logging
import base64
import tempfile
import asyncio
from playwright.async_api import async_playwright
import io
from PIL import Image

app = Flask(__name__)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Configuration
PORT = int(os.getenv('PORT', 8082))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

class MindMapImageGenerator:
    def __init__(self):
        # Remove persistent state to avoid event loop conflicts
        pass
        
    async def generate_image(self, mind_map_json, width=1200, height=800, format='png'):
        """Generate PNG image from mind map JSON with fresh browser instance"""
        playwright = None
        browser = None
        page = None
        
        try:
            logger.debug("Starting fresh Playwright browser...")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--no-first-run',
                    '--no-zygote',
                    '--disable-gpu',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-extensions',
                    '--disable-plugins',
                    '--disable-default-apps'
                ]
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
            await page.set_content(html_content, wait_until='domcontentloaded')
            
            # Wait for the diagram to be rendered
            logger.debug("Waiting for diagram to be ready...")
            await page.wait_for_function("window.diagramReady === true", timeout=30000)
            
            # Take screenshot of the diagram div
            logger.debug("Taking screenshot...")
            diagram_element = await page.query_selector('#myDiagramDiv')
            if not diagram_element:
                raise Exception("Diagram element not found")
            
            # Get the bounding box and take screenshot
            screenshot_bytes = await diagram_element.screenshot(type=format)
            logger.debug(f"Screenshot taken, size: {len(screenshot_bytes)} bytes")
            
            return screenshot_bytes
            
        except Exception as e:
            logger.error(f"Error generating image: {e}")
            raise
        finally:
            # Always cleanup everything
            try:
                if page:
                    await page.close()
                if browser:
                    await browser.close()
                if playwright:
                    await playwright.stop()
                logger.debug("Browser resources cleaned up")
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
    
    def _create_html_content(self, mind_map_json, width, height):
        """Create HTML content with GoJS mind map"""
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
            if (root === "null") return;
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

# Global image generator instance
image_generator = MindMapImageGenerator()

def run_async_safely(coro):
    """Safely run async coroutine in Flask route"""
    import threading
    import concurrent.futures
    
    def run_in_thread():
        """Run coroutine in a separate thread with its own event loop"""
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
        return future.result(timeout=60)  # 60 second timeout

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "mindcraft-image-generator"})

@app.route('/generate_image', methods=['POST'])
def generate_image():
    """Generate PNG image from mind map JSON"""
    logger.debug("Received request to generate mind map image")
    
    try:
        # Get JSON data from request
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        mind_map_data = request_data.get('mind_map_data')
        if not mind_map_data:
            return jsonify({'error': 'mind_map_data not provided'}), 400
        
        # Optional parameters
        width = request_data.get('width', 1200)
        height = request_data.get('height', 800)
        format_type = request_data.get('format', 'png')
        
        logger.debug(f"Generating image with dimensions: {width}x{height}")
        logger.debug(f"Mind map has {len(mind_map_data.get('nodeDataArray', []))} nodes")
        
        # Generate image using improved async handling
        image_bytes = run_async_safely(
            image_generator.generate_image(mind_map_data, width, height, format_type)
        )
        
        # Return image as response
        return send_file(
            io.BytesIO(image_bytes),
            mimetype=f'image/{format_type}',
            as_attachment=True,
            download_name=f'mindmap.{format_type}'
        )
        
    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate_image_base64', methods=['POST'])
def generate_image_base64():
    """Generate PNG image from mind map JSON and return as base64"""
    logger.debug("Received request to generate mind map image as base64")
    
    try:
        # Get JSON data from request
        request_data = request.get_json()
        if not request_data:
            return jsonify({'error': 'No JSON data provided'}), 400
        
        mind_map_data = request_data.get('mind_map_data')
        if not mind_map_data:
            return jsonify({'error': 'mind_map_data not provided'}), 400
        
        # Optional parameters
        width = request_data.get('width', 1200)
        height = request_data.get('height', 800)
        format_type = request_data.get('format', 'png')
        
        logger.debug(f"Generating base64 image with dimensions: {width}x{height}")
        
        # Generate image using improved async handling
        image_bytes = run_async_safely(
            image_generator.generate_image(mind_map_data, width, height, format_type)
        )
        
        # Convert to base64
        image_base64 = base64.b64encode(image_bytes).decode('utf-8')
        
        return jsonify({
            'image_base64': image_base64,
            'format': format_type,
            'width': width,
            'height': height
        })
        
    except Exception as e:
        logger.error(f"Error generating base64 image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/test_simple', methods=['GET'])
def test_simple():
    """Simple test endpoint without image generation"""
    logger.debug("Simple test endpoint called")
    return jsonify({
        "status": "success",
        "message": "Flask app is working",
        "service": "mindcraft-image-generator"
    })

@app.route('/test_image', methods=['GET'])
def test_image():
    """Test endpoint to generate a sample mind map image"""
    logger.debug("Test image generation endpoint called")
    
    # Sample mind map data
    sample_data = {
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
      },
      {
        "key": 26,
        "parent": 21,
        "text": "التجديد والإبداع",
        "brush": "palevioletred",
        "dir": "right"
      },
      {
        "key": 27,
        "parent": 26,
        "text": "الخيال",
        "brush": "palevioletred",
        "dir": "null"
      },
      {
        "key": 28,
        "parent": 26,
        "text": "الديباجة المشرقة",
        "brush": "palevioletred",
        "dir": "null"
      },
      {
        "key": 29,
        "parent": 21,
        "text": "الأوزان والتفعيلة",
        "brush": "darkseagreen",
        "dir": "left"
      },
      {
        "key": 30,
        "parent": 29,
        "text": "الشعراء المهجريين",
        "brush": "darkseagreen",
        "dir": "null"
      },
      {
        "key": 31,
        "parent": 30,
        "text": "محمد سعيد الجيل",
        "brush": "lightsteelblue",
        "dir": "null"
      },
      {
        "key": 32,
        "parent": 30,
        "text": "غازي",
        "brush": "lightsteelblue",
        "dir": "null"
      },
      {
        "key": 33,
        "parent": 21,
        "text": "المراحل",
        "brush": "lightcoral",
        "dir": "right"
      },
      {
        "key": 34,
        "parent": 33,
        "text": "المرحلة الثانية",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 35,
        "parent": 34,
        "text": "التعبير عن القضايا الإنسانية",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 36,
        "parent": 34,
        "text": "الأسلوب",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 37,
        "parent": 34,
        "text": "الشعراء البارزين",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 38,
        "parent": 33,
        "text": "المرحلة الأولى",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 39,
        "parent": 38,
        "text": "الشعر الوجداني",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 40,
        "parent": 38,
        "text": "الشعر الفردي",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 41,
        "parent": 38,
        "text": "حسن عواد",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 42,
        "parent": 38,
        "text": "محمد حسن فقي",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 43,
        "parent": 38,
        "text": "أحمد عبد الجبار",
        "brush": "lightpink",
        "dir": "null"
      },
      {
        "key": 44,
        "parent": 0,
        "text": "مقدمة النص",
        "dir": "right",
        "brush": "skyblue"
      },
      {
        "key": 45,
        "parent": 44,
        "text": "الحروف العربية",
        "brush": "skyblue",
        "dir": "left"
      },
      {
        "key": 46,
        "parent": 45,
        "text": "وضوح الحروف",
        "brush": "lightcoral",
        "dir": "left"
      },
      {
        "key": 47,
        "parent": 45,
        "text": "شكل الحروف",
        "brush": "lightcoral",
        "dir": "left"
      },
      {
        "key": 48,
        "parent": 44,
        "text": "أجزاء النص",
        "brush": "palevioletred",
        "dir": "right"
      },
      {
        "key": 49,
        "parent": 48,
        "text": "النهاية",
        "brush": "plum",
        "dir": "left"
      },
      {
        "key": 50,
        "parent": 48,
        "text": "البداية",
        "brush": "plum",
        "dir": "left"
      },
      {
        "key": 51,
        "parent": 44,
        "text": "مظهر النص",
        "brush": "darkseagreen",
        "dir": "left"
      },
      {
        "key": 52,
        "parent": 51,
        "text": "تناسق الخط",
        "brush": "lightpink",
        "dir": "right"
      },
      {
        "key": 53,
        "parent": 51,
        "text": "أسلوب الكتابة",
        "brush": "lightpink",
        "dir": "right"
      },
      {
        "key": 54,
        "parent": 44,
        "text": "جودة الكتابة",
        "brush": "lightsteelblue",
        "dir": "right"
      },
      {
        "key": 55,
        "parent": 54,
        "text": "اهتمام بالتفاصيل",
        "brush": "lightcoral",
        "dir": "right"
      },
      {
        "key": 56,
        "parent": 54,
        "text": "وضوح النص",
        "brush": "lightcoral",
        "dir": "right"
      }
    ]
    }
    
    try:
        # Generate image using improved async handling
        image_bytes = run_async_safely(
            image_generator.generate_image(sample_data, 1200, 800, 'png')
        )
        
        return send_file(
            io.BytesIO(image_bytes),
            mimetype='image/png',
            as_attachment=True,
            download_name='test_mindmap.png'
        )
        
    except Exception as e:
        logger.error(f"Error in test image generation: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=DEBUG)
