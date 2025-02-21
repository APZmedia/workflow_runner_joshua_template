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

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_FILE_STEP1 = os.path.join(DATA_DIR, "1-Text Analysis v2.json")
JSON_FILE_STEP2 = os.path.join(DATA_DIR, "Demo-Step02-api.json")  # Updated file for API workflow

# Ensure necessary directories exist
os.makedirs(DATA_DIR, exist_ok=True)

def load_workflow(file_path):
    """Loads a workflow JSON file."""
    if not os.path.exists(file_path):
        return {"error": f"Workflow JSON file {file_path} not found."}
    
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def update_workflow(workflow, input_text):
    """
    Update the workflow JSON with the user prompt.
    
    For the API workflow, update the node with class_type 'Text Multiline'
    (node "248") by setting its 'text' input to the provided input_text.
    """
    for node_id, node in workflow.items():
        if node.get("class_type") == "Text Multiline":
            inputs = node.get("inputs", {})
            inputs["text"] = input_text
            node["inputs"] = inputs
    return workflow

def process_workflow(input_text):
    """Processes Step01 (News Analysis)."""
    workflow = load_workflow(JSON_FILE_STEP1)
    if "error" in workflow:
        return workflow["error"]

    updated_workflow = update_workflow(workflow, input_text)
    full_result = execute_workflow(updated_workflow)

    # Process output from the original workflow structure
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
    """Processes Step02 (Carousel Text Generation) using the API JSON."""
    workflow = load_workflow(JSON_FILE_STEP2)
    if "error" in workflow:
        return workflow["error"]

    updated_workflow = update_workflow(workflow, input_text)
    carousel_result = execute_carousel_workflow(updated_workflow)
    return json.dumps(carousel_result, indent=2)

# Gradio UI with two tabs (Step01 & Step02)
iface = gr.TabbedInterface(
    [
        gr.Interface(
            fn=process_workflow,
            inputs=[gr.Textbox(label="News Prompt", lines=3, placeholder="Enter a news prompt")],
            outputs="text",
            title="Step 01 - News Analysis",
            description="Enter a news prompt and generate a response."
        ),
        gr.Interface(
            fn=process_carousel_workflow,
            inputs=[gr.Textbox(label="Carousel Prompt", lines=3, placeholder="Enter a carousel prompt")],
            outputs="text",
            title="Step 02 - Carousel Text Generation",
            description="Enter a prompt and generate a structured JSON output for carousel text."
        )
    ]
)

if __name__ == "__main__":
    iface.launch()
