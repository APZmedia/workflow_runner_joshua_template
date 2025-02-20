import requests
import websocket
import json
import uuid
import time

COMFYUI_ENDPOINT = "127.0.0.1:8188"

def join_output_text(text_list):
    """
    Joins a list of individual characters into a single string.
    
    Args:
        text_list (list): A list of characters.
        
    Returns:
        str: The joined string.
    """
    joined_text = "".join(text_list)
    print("Joined text:", joined_text)
    return joined_text

def print_progress(value, max_value):
    """Optional: Print a basic progress bar."""
    bar_length = 40  # Length of the progress bar
    ratio = float(value) / float(max_value) if max_value != 0 else 0
    filled = int(ratio * bar_length)
    bar = '█' * filled + '-' * (bar_length - filled)
    print(f"\rProgress: [{bar}] {int(ratio * 100)}%", end='', flush=True)
    if value >= max_value:
        print("\nPrompt complete!")  # line break at 100%

def establish_connection():
    """Establish a WebSocket connection to ComfyUI."""
    client_id = str(uuid.uuid4())
    ws_url = f"ws://{COMFYUI_ENDPOINT}/ws?clientId={client_id}"
    print(f"[establish_connection] client_id = {client_id}")
    print(f"[establish_connection] Connecting to: {ws_url}")

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    return ws, client_id

# Global variables to share state between callbacks
TRACKING_PROMPT_ID = None
WORKFLOW_DONE = False

def on_open(ws):
    print("[on_open] WebSocket connection opened.")

def on_message(ws, message):
    """Handles incoming WebSocket messages."""
    global WORKFLOW_DONE

    # Debug log
    print(f"[on_message] Raw message: {message}")

    try:
        data = json.loads(message)
        mtype = data.get("type")

        # 1) Progress updates
        if mtype == "progress":
            prog_data = data["data"]
            val = prog_data["value"]
            mx  = prog_data["max"]
            print_progress(val, mx)

        # 2) Status updates indicating completion
        elif mtype == "status":
            status_data = data.get("data", {}).get("status", {})
            exec_info = status_data.get("exec_info", {})
            queue_remaining = exec_info.get("queue_remaining")
            print(f"[on_message] Queue remaining: {queue_remaining}")
            if queue_remaining == 0:
                print("\n[on_message] Workflow is complete (queue_remaining=0).")
                # Wait briefly to ensure the job has fully finished processing
                time.sleep(1)
                WORKFLOW_DONE = True
                ws.close()

        # 3) Execution updates (fallback)
        elif mtype == "executing":
            exec_data = data.get("data", {})
            prompt_id = exec_data.get("prompt_id")
            node      = exec_data.get("node")
            if node is None and prompt_id == TRACKING_PROMPT_ID:
                print(f"\n[on_message] Workflow {prompt_id} is fully executed.")
                WORKFLOW_DONE = True
                ws.close()

    except Exception as e:
        print(f"[on_message] Error: {e}")

def on_error(ws, error):
    print(f"[on_error] WebSocket error: {error}")

def on_close(ws, close_status_code, close_msg):
    print(f"[on_close] WebSocket closed. Status: {close_status_code}, Msg: {close_msg}")

def queue_prompt(prompt, client_id):
    """Queue a workflow for execution and log full response."""
    data = {"prompt": prompt, "client_id": client_id}
    headers = {"Content-Type": "application/json"}

    print("[queue_prompt] Sending workflow to ComfyUI:")
    print(json.dumps(data, indent=2))

    post_url = f"http://{COMFYUI_ENDPOINT}/prompt"
    print(f"[queue_prompt] POST URL: {post_url}")
    response = requests.post(post_url, json=data, headers=headers)

    print(f"[queue_prompt] Response Status: {response.status_code}")
    print(f"[queue_prompt] Response Content: {response.text}")

    if response.status_code == 200 and response.text.strip():
        prompt_id = response.json().get("prompt_id")
        print(f"[queue_prompt] Extracted prompt_id: {prompt_id}")
        return prompt_id
    else:
        print("[queue_prompt] No valid prompt_id returned.")
        return None

def get_history(prompt_id):
    """Fetch the output data for a completed workflow."""
    get_url = f"http://{COMFYUI_ENDPOINT}/history/{prompt_id}"
    print(f"[get_history] GET URL: {get_url}")

    response = requests.get(get_url)
    print(f"[get_history] Status: {response.status_code}")
    print(f"[get_history] Content: {response.text}")

    if response.status_code == 200:
        return response.json()
    return {"error": f"Failed to fetch history (HTTP {response.status_code})."}

def track_progress(ws):
    """Run the WebSocket event loop until it's closed."""
    print("[track_progress] Starting run_forever() for WebSocket events...")
    ws.run_forever()
    print("[track_progress] WebSocket loop has ended.")

def execute_workflow(workflow_data):
    global TRACKING_PROMPT_ID, WORKFLOW_DONE
    WORKFLOW_DONE = False

    ws, client_id = establish_connection()
    try:
        print("[execute_workflow] Queuing workflow...")
        prompt_id = queue_prompt(workflow_data, client_id)
        if not prompt_id:
            return {"error": "Failed to queue job"}

        TRACKING_PROMPT_ID = prompt_id
        print(f"[execute_workflow] Tracking progress for prompt_id={prompt_id}")
        track_progress(ws)  # Blocks until the WebSocket loop ends

        if WORKFLOW_DONE:
            print("[execute_workflow] Fetching output data via /history.")
            history_response = get_history(prompt_id)
            print("[execute_workflow] Raw history_response:", history_response)

            # --- The code to unify or rejoin text ---
            if prompt_id in history_response:
                # If it's nested under the prompt_id key
                workflow_result = history_response[prompt_id]
                rejoin_text_fields(workflow_result)
                return workflow_result
            else:
                # The entire thing is the final structure
                rejoin_text_fields(history_response)
                return history_response

        else:
            return {"error": "Workflow never reached completion."}

    finally:
        print("[execute_workflow] Closing WebSocket.")
        ws.close()

def rejoin_text_fields(data):
    """Recursively look for 'INPUT': [list of chars] and rejoin them into a single string."""
    if not isinstance(data, dict):
        return
    for key, val in data.items():
        if isinstance(val, dict):
            if "INPUT" in val and isinstance(val["INPUT"], list):
                # join the array of chars into a single string
                val["INPUT"] = "".join(str(x) for x in val["INPUT"])
            # Recurse deeper
            rejoin_text_fields(val)
        elif isinstance(val, list):
            # Possibly sub-items. Recurse each element
            for item in val:
                rejoin_text_fields(item)



# Simple test for demonstration
if __name__ == "__main__":
    sample_workflow = {
        "nodes": [
            {"id": "1", "class_type": "String", "inputs": {"String": "Test input"}}
        ]
    }
    result = execute_workflow(sample_workflow)
    print("[__main__] Final result:", json.dumps(result, indent=2))
