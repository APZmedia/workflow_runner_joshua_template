import os
import sys
import json
import gradio as gr

# Import your comfyui_client code
from modules.comfyui_client import execute_workflow, execute_carousel_workflow

# If using a venv
VENV_DIR = os.path.join(os.path.dirname(__file__), "venv")
if sys.prefix != VENV_DIR:
    activate_script = os.path.join(VENV_DIR, "Scripts" if os.name=="nt" else "bin", "activate_this.py")
    if os.path.exists(activate_script):
        exec(open(activate_script).read(), {'__file__': activate_script})

# File paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
JSON_FILE_STEP1 = os.path.join(DATA_DIR, "1-Text Analysis v2.json")
JSON_FILE_STEP2 = os.path.join(DATA_DIR, "Demo-Step02-api.json")
JSON_FILE_STEP3 = os.path.join(DATA_DIR, "Step3-4Agri-carousel-A-v2-api.json")

os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------- Step01 & Step02 logic ---------------------------- #

def load_workflow(file_path):
    if not os.path.exists(file_path):
        return {"error": f"Workflow JSON file {file_path} not found."}
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def update_workflow(workflow, input_text):
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == "Text Multiline":
            node["inputs"]["text"] = input_text
    return workflow

def process_workflow(input_text):
    """
    Step01: load JSON_FILE_STEP1, call execute_workflow, look for node '4' => 'INPUT'
    """
    wf_data = load_workflow(JSON_FILE_STEP1)
    if "error" in wf_data:
        return wf_data["error"]
    updated = update_workflow(wf_data, input_text)
    result = execute_workflow(updated)
    if isinstance(result, dict):
        if "outputs" in result and "4" in result["outputs"]:
            node4 = result["outputs"]["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)
        elif "4" in result:
            node4 = result["4"]
            if "INPUT" in node4:
                return json.dumps({"result": node4["INPUT"]}, indent=2)
    return json.dumps({"error": "INPUT not found"}, indent=2)

def process_carousel_workflow(input_text):
    """
    Step02: load JSON_FILE_STEP2, call execute_carousel_workflow
    """
    wf_data = load_workflow(JSON_FILE_STEP2)
    if "error" in wf_data:
        return wf_data["error"]
    updated = update_workflow(wf_data, input_text)
    result = execute_carousel_workflow(updated)
    return json.dumps(result, indent=2)

# ---------------------- Step01 "Copy the result" => Step02 input ---------------------- #

def copy_step01_to_step02(json_str):
    """
    Step01 has output like {"result": "...some text..."}
    We parse & remove \n, quotes, asterisks => final text for Step02 input
    """
    try:
        data = json.loads(json_str)
        val = data.get("result","")
        return " ".join(val.split()).replace('"',"").replace("*","")
    except:
        return ""

# ---------------------- Step02 "Copy generated content" => Step03 state ---------------------- #

def copy_generated_content_step02(json_str):
    """
    Step02 output is:
      {
        "Title": "...",
        "Subtitle": "...",
        "Text01": "...",
        "Text02": "...",
        "Text03": "...",
        "Hashtag": "..."
      }
    We parse & create a dict with Title,Subtitle,Text01,Text02,Text03
    plus cta & post_caption, then store in step3_data
    """
    try:
        data = json.loads(json_str)
        def c(t):
            return " ".join(t.split()).replace('"',"").replace("*","")
        title    = c(data.get("Title",""))
        subtitle = c(data.get("Subtitle",""))
        text01   = c(data.get("Text01",""))
        text02   = c(data.get("Text02",""))
        text03   = c(data.get("Text03",""))
        hashtag  = c(data.get("Hashtag",""))
        cta = "Enter your CTA"
        post_caption = hashtag
        return {
            "title": title,
            "subtitle": subtitle,
            "text01": text01,
            "text02": text02,
            "text03": text03,
            "cta": cta,
            "post_caption": post_caption
        }
    except:
        return {
            "title": "",
            "subtitle": "",
            "text01": "",
            "text02": "",
            "text03": "",
            "cta": "",
            "post_caption": ""
        }

# ---------------------- Step03 "Generate images" => Step3 JSON & ComfyUI ---------------------- #

def generate_images_step3(title, subtitle, text01, text02, text03, cta, post_caption, ref_image):
    """
    1) load JSON_FILE_STEP3
    2) update nodes (129 => title, etc.)
    3) set node '137' => ref_image
    4) call execute_workflow => returns images from nodes 298,297,302
    """
    wf_data = load_workflow(JSON_FILE_STEP3)
    if "error" in wf_data:
        return None, None, None

    # Adjust IDs as needed
    text_map = {
        "129": title,
        "130": subtitle,
        "142": text01,
        "144": text02,
        "146": text03,
        "226": cta,
        "219": post_caption
    }
    for nid, node in wf_data.items():
        if isinstance(node, dict) and node.get("class_type") == "Text Multiline":
            if nid in text_map:
                node["inputs"]["text"] = text_map[nid]

    # Node "137" => reference image
    if ref_image and isinstance(ref_image, str):
        if "137" in wf_data:
            wf_data["137"]["inputs"]["image"] = ref_image

    # Execute ComfyUI workflow => logs to terminal
    result = execute_workflow(wf_data)

    # Extract images from e.g. "298","297","302"
    i1 = result.get("298",{}).get("INPUT")
    i2 = result.get("297",{}).get("INPUT")
    i3 = result.get("302",{}).get("INPUT")
    return i1, i2, i3

# ---------------------- BUILD THE GRADIO UI ---------------------- #

with gr.Blocks(css="""
  .two-col { display: flex; gap: 15px; }
""") as demo:
    step3_data = gr.State({})  # For storing final 7 fields from Step02

    with gr.Tabs():
        # STEP 01
        with gr.TabItem("Step 01 - News Analysis"):
            gr.Markdown("**Step01**: Enter a news prompt, generate a JSON, then click 'Copy the result' to fill Step02.")
            with gr.Row():
                with gr.Column():
                    step1_input = gr.Textbox(label="News Prompt", lines=10)
                    step1_button = gr.Button("Generate Step01 Output")
                with gr.Column():
                    step1_output = gr.Textbox(label="Step01 JSON Output", lines=10, interactive=False)
                    # The original Step01 button
                    copy01_button = gr.Button("Copy the result")

            step1_button.click(fn=process_workflow, inputs=step1_input, outputs=step1_output)
            # Copy cleaned text => Step02 input
            copy01_button.click(fn=copy_step01_to_step02, inputs=step1_output, outputs=None)

        # STEP 02
        with gr.TabItem("Step 02 - Carousel Text Generation"):
            gr.Markdown("**Step02**: Adjust the prompt if needed, generate the final JSON, then 'Copy generated content' for Step03.")
            with gr.Row():
                with gr.Column():
                    step2_input = gr.Textbox(label="Carousel Prompt", lines=10)
                    step2_button = gr.Button("Generate Carousel Output")
                with gr.Column():
                    step2_output = gr.Textbox(label="Carousel JSON Output", lines=10, interactive=False)
                    copy02_button = gr.Button("Copy generated content")

            # Step02 logic
            step2_button.click(fn=process_carousel_workflow, inputs=step2_input, outputs=step2_output)

            # On copy, parse the JSON => step3_data
            copy02_button.click(fn=copy_generated_content_step02, inputs=step2_output, outputs=step3_data)

        # STEP 03
        with gr.TabItem("Step 03 - Final Carousel & Images"):
            gr.Markdown("**Step03**: Fill in Title, etc., plus ref image, then 'Generate carousel images'.")
            with gr.Row():
                with gr.Column():
                    # 7 fields
                    title_in        = gr.Textbox(label="Title", lines=2)
                    subtitle_in     = gr.Textbox(label="Subtitle", lines=2)
                    text01_in       = gr.Textbox(label="Text01", lines=3)
                    text02_in       = gr.Textbox(label="Text02", lines=3)
                    text03_in       = gr.Textbox(label="Text03", lines=3)
                    cta_in          = gr.Textbox(label="Call to Action", lines=2)
                    post_caption_in = gr.Textbox(label="Post Caption", lines=2)

                    update_btn = gr.Button("Update Step03 from Step02 data")
                with gr.Column():
                    ref_image = gr.Image(label="Reference Image", type="filepath")
            
            generate_btn = gr.Button("Generate carousel images")
            with gr.Row():
                img1 = gr.Image(label="Preview 1")
                img2 = gr.Image(label="Preview 2")
                img3 = gr.Image(label="Preview 3")

            # Fill Step03 fields from step3_data
            def fill_step03(d):
                return (
                    d.get("title",""), d.get("subtitle",""),
                    d.get("text01",""), d.get("text02",""), d.get("text03",""),
                    d.get("cta",""), d.get("post_caption","")
                )
            update_btn.click(fn=fill_step03, inputs=step3_data, outputs=[
                title_in, subtitle_in, text01_in, text02_in, text03_in, cta_in, post_caption_in
            ])

            # Generate images => calls Step3
            generate_btn.click(fn=generate_images_step3, inputs=[
                title_in, subtitle_in, text01_in, text02_in, text03_in,
                cta_in, post_caption_in, ref_image
            ], outputs=[img1, img2, img3])

    # The final trick: We want the Step01 button to set Step02 input directly.
    # We do that with a .then() or by hooking the "change" event. 
    # Simpler is to do a small JS or do "manually" below.

    # We'll add a small bridging function:
    def step01_to_step02_bridge(x):
        # x is the cleaned text from Step01
        return x
    
    # We'll create a hidden intermediate to store the cleaned text.
    hidden_state = gr.State("")  # store cleaned text from Step01

    # Now we re-wire the Step01 button to store in hidden_state, then .then() to set step2_input
    copy01_button.click(fn=copy_step01_to_step02, inputs=step1_output, outputs=hidden_state)\
                 .then(fn=step01_to_step02_bridge, inputs=hidden_state, outputs=step2_input)

demo.launch()
