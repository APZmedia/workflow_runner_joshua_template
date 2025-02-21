import requests
import websocket
import json
import uuid
import time

COMFYUI_ENDPOINT = "127.0.0.1:8188"

def join_output_text(text_list):
    """Joins a list of individual characters into a single string."""
    joined_text = "".join(text_list)
    print("Joined text:", joined_text)
    return joined_text

def print_progress(value, max_value):
    bar_length = 40
    ratio = float(value) / float(max_value) if max_value != 0 else 0
    filled = int(ratio * bar_length)
    bar = '█' * filled + '-' * (bar_length - filled)
    print(f"\rProgress: [{bar}] {int(ratio * 100)}%", end='', flush=True)
    if value >= max_value:
        print("\nPrompt complete!")

def establish_connection():
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

TRACKING_PROMPT_ID = None
WORKFLOW_DONE = False

def on_open(ws):
    print("[on_open] WebSocket connection opened.")

def on_message(ws, message):
    global WORKFLOW_DONE
    print(f"[on_message] Raw message: {message}")
    try:
        data = json.loads(message)
        mtype = data.get("type")
        if mtype == "progress":
            prog_data = data["data"]
            print_progress(prog_data["value"], prog_data["max"])
        elif mtype == "status":
            status_data = data.get("data", {}).get("status", {})
            queue_remaining = status_data.get("exec_info", {}).get("queue_remaining")
            print(f"[on_message] Queue remaining: {queue_remaining}")
            if queue_remaining == 0:
                print("\n[on_message] Workflow is complete (queue_remaining=0).")
                time.sleep(1)
                WORKFLOW_DONE = True
                ws.close()
        elif mtype == "executing":
            exec_data = data.get("data", {})
            prompt_id = exec_data.get("prompt_id")
            if prompt_id == TRACKING_PROMPT_ID and exec_data.get("node") is None:
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
    get_url = f"http://{COMFYUI_ENDPOINT}/history/{prompt_id}"
    print(f"[get_history] GET URL: {get_url}")
    response = requests.get(get_url)
    print(f"[get_history] Status: {response.status_code}")
    print(f"[get_history] Content: {response.text}")
    if response.status_code == 200:
        return response.json()
    return {"error": f"Failed to fetch history (HTTP {response.status_code})."}

def track_progress(ws):
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
        track_progress(ws)
        if WORKFLOW_DONE:
            print("[execute_workflow] Fetching output data via /history.")
            history_response = get_history(prompt_id)
            print("[execute_workflow] Raw history_response:", history_response)
            if prompt_id in history_response:
                workflow_result = history_response[prompt_id]
                rejoin_text_fields(workflow_result)
                return workflow_result
            else:
                rejoin_text_fields(history_response)
                return history_response
        else:
            return {"error": "Workflow never reached completion."}
    finally:
        print("[execute_workflow] Closing WebSocket.")
        ws.close()

def rejoin_text_fields(data):
    if not isinstance(data, dict):
        return
    for key, val in data.items():
        if isinstance(val, dict):
            if "INPUT" in val and isinstance(val["INPUT"], list):
                val["INPUT"] = "".join(str(x) for x in val["INPUT"])
            rejoin_text_fields(val)
        elif isinstance(val, list):
            for item in val:
                rejoin_text_fields(item)

def process_carousel_result(result):
    """
    Processes the ComfyUI output to extract carousel text fields.
    Expected output: a JSON string in the display node (node "25")
    with keys "Title", "Subtitle", "Text01", "Text02", "Text03", "Hashtag".
    """
    print("\n=== Debug: Checking result structure ===")
    print(json.dumps(result, indent=2))
    
    if "error" in result:
        return {
            "Title": "[Title not generated]",
            "Subtitle": "[Subtitle not generated]",
            "Text01": "[Text01 not generated]",
            "Text02": "[Text02 not generated]",
            "Text03": "[Text03 not generated]",
            "Hashtag": "[Hashtag not generated]"
        }
    
    # Use outputs if available
    if "outputs" in result:
        result = result["outputs"]
    
    display_node = result.get("25", {})
    output_text = ""
    if "INPUT" in display_node:
        value = display_node["INPUT"]
        if isinstance(value, list):
            output_text = "".join(value)
        else:
            output_text = value
    else:
        output_text = "{}"
    
    try:
        carousel_data = json.loads(output_text)
    except Exception as e:
        print("Error parsing JSON from output:", e)
        carousel_data = {}
    
    expected_keys = ["Title", "Subtitle", "Text01", "Text02", "Text03", "Hashtag"]
    output = {}
    for key in expected_keys:
        output[key] = carousel_data.get(key, f"[{key} not generated]")
    return output

def execute_carousel_workflow(workflow_data):
    result = execute_workflow(workflow_data)
    print("\n=== Raw Output from ComfyUI ===")
    print(json.dumps(result, indent=2))
    if not result:
        print("❌ Error: No result received from execute_workflow")
        return {"error": "No result received"}
    carousel_text = process_carousel_result(result)
    print("\n=== Processed Carousel Output ===")
    print(json.dumps(carousel_text, indent=2))
    return carousel_text

if __name__ == "__main__":
    # Optional test code here.
    sample_carousel = {
        "25": {
            "INPUT": list('{"Title": "The Ocean\'s Fury","Subtitle": "Oceans absorb 90% of emissions, fueling extreme weather.","Text01": "The ocean\'s surface temperature has surged by 0.5°C over the past century, equivalent to a nuclear explosion every second. This alarming trend is a harbinger of more frequent and intense natural disasters.","Text02": "A study reveals oceans\' accelerating heat absorption, impacting weather patterns and marine ecosystems.","Text03": "Our oceans are on fire. It\'s time to act against climate change for a sustainable future.","Hashtag": "#OceanWarming"}')
        }
    }
    carousel_result = process_carousel_result(sample_carousel)
    print("Carousel Result:", json.dumps(carousel_result, indent=2))
