#!/usr/bin/env python3
"""Offline test of comfy_workflow.convert / fill_u22 on a small hand-made workflow with the same
kinds of editor plumbing U22 uses: named Set/Get pairs, a Reroute, bypassed image slots, a seed with
its "control after generate" value, a node whose widgets are saved by name, a dynamic choice, and
a note. Exits 0 when the converted graph is what the editor would run.

    python3 series/tools/tests/test_comfy_workflow.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import comfy_workflow as cw  # noqa: E402

C = lambda *o: ["COMBO", {"options": list(o)}]          # noqa: E731
INFO = {
    "LoadImage": {"input": {"required": {"image": C("x.png"), "upload": ["IMAGEUPLOAD", {}]}}},
    "CR Prompt Text": {"input": {"required": {"prompt": ["STRING", {"multiline": True}]}}},
    "PrimitiveFloat": {"input": {"required": {"value": ["FLOAT", {"default": 5}]}}},
    "RandomNoise": {"input": {"required": {"noise_seed": ["INT", {"default": 0, "control_after_generate": True}]}}},
    "ResolutionSelector": {"input": {"required": {"aspect_ratio": C("16:9 (Widescreen)", "9:16 (Portrait Widescreen)"), "megapixels": ["FLOAT", {}]}}},
    "Gen": {"input": {"required": {"prompt": ["STRING", {}], "seconds": ["FLOAT", {}], "w": ["INT", {}], "noise": ["NOISE", {}]},
                      "optional": {"ref_images.ref_image_0": ["IMAGE", {}], "ref_images.ref_image_1": ["IMAGE", {}]}}},
    "Up": {"input": {"required": {"latent": ["*", {}], "mode": ["COMFY_DYNAMICCOMBO_V3", {"options": [
        {"key": "scale by multiplier", "inputs": {"required": {"scale": ["FLOAT", {}]}}}]}], "align": ["INT", {}]}}},
    "VHS_VideoCombine": {"input": {"required": {"images": ["IMAGE", {}], "frame_rate": ["FLOAT", {}], "filename_prefix": ["STRING", {}],
                                                "save_output": ["BOOLEAN", {}]}}, "output_node": True},
}


def node(i, t, inputs=(), widgets=None, mode=0, title="", outputs=()):
    return {"id": i, "type": t, "mode": mode, "title": title, "inputs": list(inputs), "outputs": list(outputs), "widgets_values": widgets}


WF = {"nodes": [
    node(1, "LoadImage", [{"name": "image", "widget": {"name": "image"}}, {"name": "upload", "widget": {"name": "upload"}}], ["a.png", "image"],
         outputs=[{"type": "IMAGE"}]),
    node(2, "SetNode", [{"name": "IMAGE", "link": 1}], ["图像1"]),
    node(3, "LoadImage", [{"name": "image", "widget": {"name": "image"}}], ["None", "image"], mode=4, outputs=[{"type": "IMAGE"}]),
    node(4, "SetNode", [{"name": "IMAGE", "link": 2}], ["图像2"], mode=4),
    node(5, "GetNode", [], ["图像1"], outputs=[{"type": "IMAGE"}]),
    node(6, "GetNode", [], ["图像2"], outputs=[{"type": "IMAGE"}]),
    node(7, "CR Prompt Text", [], ["old prompt"], outputs=[{"type": "STRING"}]),
    node(8, "PrimitiveFloat", [{"name": "value", "widget": {"name": "value"}}], [10], title="视频时长（秒）", outputs=[{"type": "FLOAT"}]),
    node(9, "RandomNoise", [{"name": "noise_seed", "widget": {"name": "noise_seed"}}], [42, "randomize"], outputs=[{"type": "NOISE"}]),
    node(10, "Reroute", [{"name": "", "link": 5}], None, outputs=[{"type": "NOISE"}]),
    node(11, "Gen", [{"name": "prompt", "link": 3}, {"name": "seconds", "link": 4}, {"name": "noise", "link": 6},
                     {"name": "ref_images.ref_image_0", "link": 7}, {"name": "ref_images.ref_image_1", "link": 8},
                     {"name": "w", "widget": {"name": "w"}, "link": 12}], [768], outputs=[{"type": "LATENT"}]),
    node(12, "Up", [{"name": "latent", "link": 9}, {"name": "mode.scale", "widget": {"name": "mode.scale"}}], ["scale by multiplier", 1.5, 32],
         outputs=[{"type": "LATENT"}]),
    node(13, "VHS_VideoCombine", [{"name": "images", "link": 10}],
         {"frame_rate": 24, "filename_prefix": "H3", "save_output": True, "videopreview": {"hidden": False}}),
    node(14, "Note", [], ["a note"]),
    node(15, "ResolutionSelector", [], ["16:9 (Widescreen)", 0.5], outputs=[{"type": "INT"}]),
    node(16, "VHS_VideoCombine", [{"name": "images", "link": 11}], {"frame_rate": 24, "filename_prefix": "draft", "save_output": False}),
], "links": [[1, 1, 0, 2, 0, "IMAGE"], [2, 3, 0, 4, 0, "IMAGE"], [3, 7, 0, 11, 0, "STRING"], [4, 8, 0, 11, 1, "FLOAT"],
             [5, 9, 0, 10, 0, "NOISE"], [6, 10, 0, 11, 2, "NOISE"], [7, 5, 0, 11, 3, "IMAGE"], [8, 6, 0, 11, 4, "IMAGE"],
             [9, 11, 0, 12, 0, "LATENT"], [10, 12, 0, 13, 0, "IMAGE"], [11, 12, 0, 16, 0, "IMAGE"], [12, 15, 0, 11, 5, "INT"]]}

failures = []


def check(what, ok):
    print("%-4s %s" % ("ok" if ok else "FAIL", what))
    if not ok:
        failures.append(what)


INFO["ResolutionSelector"]["output_node"] = False
g = cw.fill_u22(WF, INFO, "new prompt", 7, ["up1.png", "up2.png"], 1234, prefix="film/h3")
gen = g["11"]["inputs"]
check("editor-only nodes are gone", not any(v["class_type"] in ("SetNode", "GetNode", "Reroute", "Note") for v in g.values()))
check("the prompt is filled in", g["7"]["inputs"]["prompt"] == "new prompt" and gen["prompt"] == ["7", 0])
check("the length is filled in", g["8"]["inputs"]["value"] == 7.0)
check("the seed is filled in, its control value dropped", g["9"]["inputs"] == {"noise_seed": 1234})
check("a Reroute is followed to the seed", gen["noise"] == ["9", 0])
check("Get/Set pairs are followed to the images", gen["ref_images.ref_image_0"] == ["1", 0] and gen["ref_images.ref_image_1"] == ["3", 0])
check("a bypassed slot is switched on for a second image", g["3"]["inputs"]["image"] == "up2.png" and g["1"]["inputs"]["image"] == "up1.png")
check("a widget fed by a link takes the link", gen["w"] == ["15", 0])
check("the size is set upright", g["15"]["inputs"]["aspect_ratio"].startswith("9:16"))
check("a dynamic choice keeps its option's input", g["12"]["inputs"].get("mode") == "scale by multiplier" and g["12"]["inputs"].get("mode.scale") == 1.5 and g["12"]["inputs"].get("align") == 32)
check("widgets saved by name keep their keys, not the preview", g["13"]["inputs"].get("frame_rate") == 24 and "videopreview" not in g["13"]["inputs"])
check("the saved output gets our file prefix, the draft output keeps its own", g["13"]["inputs"]["filename_prefix"] == "film/h3" and g["16"]["inputs"]["filename_prefix"] == "draft")
one = cw.fill_u22(WF, INFO, "p", 5, ["only.png"], 1)
check("with one image the second slot stays bypassed and unconnected", "3" not in one and "ref_images.ref_image_1" not in one["11"]["inputs"])
try:
    cw.fill_u22(WF, INFO, "p", 5, ["1", "2", "3"], 1)
    check("too many images is refused", False)
except cw.WorkflowError:
    check("too many images is refused", True)
missing = dict(INFO)
missing.pop("CR Prompt Text")
try:
    cw.fill_u22(WF, missing, "p", 5, ["a"], 1)
    check("a node the server lacks is refused, not skipped", False)
except cw.WorkflowError:
    check("a node the server lacks is refused, not skipped", True)
print("all steps hold" if not failures else "%d failed" % len(failures))
sys.exit(1 if failures else 0)
