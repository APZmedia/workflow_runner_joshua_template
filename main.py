import os
import sys
import json
import gradio as gr
from modules.comfyui_client import execute_workflow, execute_carousel_workflow

# Ensure we are running inside a virtual environment
VENV_DIR = os.path.join(os.path.dirname(__file__), "venv")
if sys.prefix != VENV_DIR:
    activate_script = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin", "activate_this.py")
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_FILE_STEP1 = os.path.join(DATA_DIR, "1-Text Analysis v2.json")
JSON_FILE_STEP2 = os.path.join(DATA_DIR, "Demo-Step02-api.json")  # API-style workflow

os.makedirs(DATA_DIR, exist_ok=True)

def load_workflow(file_path):
    if not os.path.exists(file_path):
        return {"error": f"Workflow JSON file {file_path} not found."}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def update_workflow(workflow, input_text):
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "Text Multiline":
            inputs = node.get("inputs", {})
            inputs["text"] = input_text
            node["inputs"] = inputs
    return workflow

def process_workflow(input_text):
    workflow = load_workflow(JSON_FILE_STEP1)
    if "error" in workflow:
        return workflow["error"]
    updated_workflow = update_workflow(workflow, input_text)
    full_result = execute_workflow(updated_workflow)
    if isinstance(full_result, dict):
        if "outputs" in full_result and "4" in full_result["outputs"]:
            node4 = full_result["outputs"]["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)
        elif "4" in full_result:
            node4 = full_result["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)
    return json.dumps({"error": "INPUT not found"}, indent=2)

def process_carousel_workflow(input_text):
    workflow = load_workflow(JSON_FILE_STEP2)
    if "error" in workflow:
        return workflow["error"]
    updated_workflow = update_workflow(workflow, input_text)
    carousel_result = execute_carousel_workflow(updated_workflow)
    return json.dumps(carousel_result, indent=2)

def extract_and_switch(json_str):
    """
    Extracts the inner text from the Step01 JSON output, cleans it, and returns it
    along with a JS snippet that attempts to switch to the Step02 tab.
    Expected input format: {"result": "some text"}
    """
    try:
        data = json.loads(json_str)
        extracted = data.get("result", "")
        # Clean text: remove newlines, extra spaces, double quotes, and asterisks.
        cleaned = " ".join(extracted.split()).replace('"', "").replace("*", "")
    except Exception as e:
        print("Error extracting result:", e)
        cleaned = ""
    js_script = """
    <script>
      setTimeout(function(){
         const tabs = document.querySelectorAll('[role="tab"]');
         if(tabs.length > 1) { tabs[1].click(); }
      }, 300);
    </script>
    """
    return cleaned, js_script

# Build the interface.
with gr.Blocks(css="""
    /* Custom CSS to ensure proper two-column layout */
    .two-col { display: flex; gap: 20px; }
    .left-col { flex: 1; }
    .right-col { flex: 1; }
    .hidden-html { display: none; }
""") as demo:
    # Hidden HTML for JS injection.
    switch_html = gr.HTML(value="", elem_classes=["hidden-html"])
    
    # Shared state for text extracted from Step01.
    step2_text_state = gr.State("")
    
    with gr.Tabs():
        with gr.TabItem("Step 01 - News Analysis"):
            gr.Markdown("Enter a news prompt and generate a JSON result.")
            # Two-column layout: left for input and button, right for output.
            with gr.Row():
                with gr.Column(variant="panel", scale=1):
                    # Large input field.
                    step1_input = gr.Textbox(label="News Prompt", lines=15, placeholder="Enter a news prompt")
                    step1_button = gr.Button("Generate Step01 Output")
                with gr.Column(variant="panel", scale=1):
                    step1_output = gr.Textbox(label="Step01 JSON Output", lines=15, interactive=False)
                    analyze_button = gr.Button("Copy the result")
            
            step1_button.click(fn=process_workflow, inputs=step1_input, outputs=step1_output)
            # Clicking analyze extracts the cleaned text and sends the JS to switch tabs.
            analyze_button.click(fn=extract_and_switch, inputs=step1_output, outputs=[step2_text_state, switch_html])
        
        with gr.TabItem("Step 02 - Carousel Text Generation"):
            gr.Markdown("The prompt below is pre-populated with the output from Step01. Edit as needed, then generate the carousel JSON output.")
            with gr.Row():
                with gr.Column(variant="panel", scale=1):
                    step2_input = gr.Textbox(label="Carousel Prompt", lines=15, placeholder="Enter a carousel prompt", value=step2_text_state)
                    step2_button = gr.Button("Generate Carousel Output")
                with gr.Column(variant="panel", scale=1):
                    step2_output = gr.Textbox(label="Carousel JSON Output", lines=15)
            step2_button.click(fn=process_carousel_workflow, inputs=step2_input, outputs=step2_output)
    
    # When the shared state changes, update the Step02 input.
    step2_text_state.change(fn=lambda x: x, inputs=step2_text_state, outputs=step2_input)
    
    switch_html  # This hidden HTML component will output the JS snippet.

demo.launch()
