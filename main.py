import os
import sys
import json
import gradio as gr
from modules.comfyui_client import execute_workflow

# Ensure we are running inside a virtual environment
VENV_DIR = os.path.join(os.path.dirname(__file__), "venv")
if sys.prefix != VENV_DIR:
    activate_script = os.path.join(VENV_DIR, "Scripts" if os.name == "nt" else "bin", "activate_this.py")
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

# Define paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_FILE = os.path.join(DATA_DIR, "1-Text Analysis v2.json")

# Ensure necessary directories exist
os.makedirs(DATA_DIR, exist_ok=True)

# Join LLM array 
def join_output_text(text_list):
    """
    Joins a list of individual characters into a single string and displays it.
    
    Args:
        text_list (list): A list of characters (e.g., ['H', 'e', 'l', 'l', 'o'])
        
    Returns:
        str: The joined string.
    """
    joined_text = "".join(text_list)
    print(joined_text)
    return joined_text


# Load workflow JSON
def load_workflow():
    """Loads the workflow JSON file."""
    if not os.path.exists(JSON_FILE):
        return {"error": "Workflow JSON file not found."}
    
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def update_workflow(workflow, input_text):
    """Update the workflow JSON with user inputs."""
    for step_data in workflow.values():
        if step_data.get("class_type") == "String":
            step_data["inputs"]["String"] = input_text
    return workflow

def process_workflow(input_text):
    workflow = load_workflow()
    if "error" in workflow:
        return workflow["error"]

    updated_workflow = update_workflow(workflow, input_text)
    full_result = execute_workflow(updated_workflow)

    # Extract only the value of "INPUT" from node "4"
    if isinstance(full_result, dict):
        if "outputs" in full_result and "4" in full_result["outputs"]:
            node4 = full_result["outputs"]["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)  # Wrap in {}

        elif "4" in full_result:
            node4 = full_result["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)  # Wrap in {}

        # If "INPUT" is not found, return a fallback message
        return json.dumps({"error": "INPUT not found"}, indent=2)

    return str(full_result)  # Default fallback if unexpected format


def process_result(result):
    """
    Processes the JSON result:
    - Looks for node "4" in the result (assuming result is a dict keyed by prompt IDs).
    - If node "4" is found and its "INPUT" field is a list, join the list into a single string.
    - Otherwise, return the full result pretty-printed.
    
    Args:
        result: The JSON result (usually a dict).
        
    Returns:
        str: The joined text from node "4", or the full JSON string.
    """
    if isinstance(result, dict):
        # Iterate over each prompt's result
        for prompt_id, data in result.items():
            if "4" in data:
                node4 = data["4"]
                input_value = node4.get("INPUT")
                if isinstance(input_value, list):
                    joined_text = "".join(input_value)
                    return joined_text
                elif input_value is not None:
                    return str(input_value)
        # If no node "4" is found, return the full JSON pretty-printed
        return json.dumps(result, indent=2)
    else:
        return str(result)

# Example usage in a Gradio interface:
if __name__ == "__main__":
    # Suppose 'result' is obtained from execute_workflow()
    sample_result = {
        "9fbb618f-cc61-42d0-8566-dbdc6a323645": {
            "prompt": [10, "9fbb618f-cc61-42d0-8566-dbdc6a323645", {
                "1": {"inputs": {"String": "Some input text..."} , "class_type": "String", "_meta": {"title": "String"}},
                "4": {"inputs": {"INPUT": ["H", "e", "l", "l", "o", " ", "W", "o", "r", "l", "d"]}, "class_type": "Griptape Display: Text", "_meta": {"title": "Griptape Display: Text"}},
            }],
            "status": {"status_str": "success", "completed": True, "messages": []},
            "meta": {"4": {"node_id": "4", "display_node": "4"}}
        }
    }
    processed = process_result(sample_result)
    print("Processed result:", processed)



# Gradio UI
iface = gr.Interface(
    fn=process_workflow,
    inputs=[gr.Textbox(label="Edit Workflow Input", lines=10)],
    outputs="text",
    title="JSON Workflow Runner with ComfyUI Integration",
    description="Edit the workflow input, queue it for execution, and see the results."
)

if __name__ == "__main__":
    iface.launch()
