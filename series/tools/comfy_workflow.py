#!/usr/bin/env python3
"""Turn a workflow saved from the ComfyUI editor into the form the /prompt endpoint runs, and fill in
a shot: prompt, length, reference images, size, seed.

    python3 comfy_workflow.py WORKFLOW.json OBJECT_INFO.json      print the converted graph (offline check)

A saved workflow is the editor's drawing: nodes with positions, links by number, values listed in
the order the widgets are drawn, and nodes that exist only in the editor. Converting it means:

  - drop editor-only nodes (notes, labels, group switches) and anything no output depends on;
  - follow Reroute nodes and named Set/Get pairs (KJNodes) back to the real node behind them;
  - a bypassed node (mode 4) passes its input of the same type straight through; when it has none,
    whatever it fed is left unconnected, exactly as the editor does; a muted node (mode 2) is gone;
  - give each widget value its input name, in the order the node's inputs list them, skipping the
    extra "control after generate" value that follows a seed;
  - check every node exists on the server.

fill_u22() knows the shape of the "U22 多参考生视频" workflow of the MINIMAX-H3提速500 app
(autodl.art app 252) and finds its parts by what they are, not by node numbers, so a re-saved copy
still works. It fails loudly when a part it needs is missing.
"""
import copy
import json
import re
import sys

EDITOR_ONLY = {"Note", "MarkdownNote", "Label (rgthree)", "Reroute", "SetNode", "GetNode", "PrimitiveNode",
               "Fast Groups Bypasser (rgthree)", "Fast Groups Muter (rgthree)", "Bookmark (rgthree)",
               "忽略多组孤海"}                                   # a group on/off switch for the editor
WIDGET_TYPES = ("COMBO", "INT", "FLOAT", "STRING", "BOOLEAN", "COMFY_DYNAMICCOMBO_V3")
UI_KEYS = ("videopreview", "choose video to upload", "choose file to upload")


class WorkflowError(RuntimeError):
    pass


def _spec(info, cls):
    return info.get(cls, {}).get("input", {})


def _all_inputs(info, cls):
    spec = _spec(info, cls)
    out = {}
    for group in ("required", "optional"):
        out.update(spec.get(group, {}))
    return out


def _has_control(spec):
    """An INT widget that the editor follows with a 'control after generate' value."""
    if not isinstance(spec, list) or len(spec) < 2 or not isinstance(spec[1], dict):
        return False
    return bool(spec[1].get("control_after_generate")) or (spec[0] == "INT" and spec[1].get("max", 0) >= 2 ** 32 - 1)


def widget_order(info, cls, values):
    """Widget names in the order the editor draws them, from the server's own definition. A dynamic
    choice is followed by the inputs of the option chosen, named "choice.input"."""
    order, i = [], 0
    for group in ("required", "optional"):
        for name, spec in _spec(info, cls).get(group, {}).items():
            kind = spec[0] if isinstance(spec, list) and spec else None
            opts = spec[1] if isinstance(spec, list) and len(spec) > 1 and isinstance(spec[1], dict) else {}
            if not (isinstance(kind, list) or kind in WIDGET_TYPES) or opts.get("forceInput"):
                continue
            order.append(name)
            chosen = values[len(order) - 1 + i] if len(order) - 1 + i < len(values) else None
            if kind == "COMFY_DYNAMICCOMBO_V3":
                option = next((o for o in opts.get("options", []) if o.get("key") == chosen), None)
                for sub in ((option or {}).get("inputs", {}).get("required") or {}):
                    order.append("%s.%s" % (name, sub))
            if _has_control(spec):
                order.append(None)                          # the "control after generate" value
    return order


def convert(wf, info):
    """-> {id: {"class_type", "inputs", "_title", "_mode"}} for /prompt."""
    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}            # id, origin, origin_slot, target, target_slot, type
    setters = {}
    for n in wf["nodes"]:
        if n["type"] == "SetNode" and n.get("widgets_values"):
            setters[n["widgets_values"][0]] = n

    def upstream(link_id, seen=()):
        """-> (node id, slot) of the real producer behind a link, or None when nothing real feeds it."""
        if link_id is None or link_id not in links or link_id in seen:
            return None
        seen = seen + (link_id,)
        _, src, slot, _, _, kind = links[link_id]
        n = nodes.get(src)
        if n is None or n.get("mode") == 2:
            return None
        t = n["type"]
        if t == "Reroute":
            return upstream((n.get("inputs") or [{}])[0].get("link"), seen)
        if t == "GetNode":
            setter = setters.get((n.get("widgets_values") or [None])[0])
            if setter is None or setter.get("mode") == 2:
                return None
            if setter.get("mode") == 4:                    # a bypassed setter still passes its value on
                pass
            return upstream((setter.get("inputs") or [{}])[0].get("link"), seen)
        if t == "SetNode":
            return upstream((n.get("inputs") or [{}])[0].get("link"), seen)
        if n.get("mode") == 4:                              # bypassed: pass the first input of the same type through
            out_type = (n.get("outputs") or [{}])[slot].get("type") if slot < len(n.get("outputs") or []) else kind
            for inp in n.get("inputs", []):
                if inp.get("link") is not None and inp.get("type") == out_type:
                    return upstream(inp["link"], seen)
            return None
        return (src, slot)

    graph = {}
    for n in wf["nodes"]:
        t = n["type"]
        if t in EDITOR_ONLY or n.get("mode") in (2, 4):
            continue
        if t not in info:
            raise WorkflowError("the server has no node %s (or its definition could not be read)" % t)
        names = _all_inputs(info, t)
        inputs = {}
        values = n.get("widgets_values")
        listed = [inp for inp in n.get("inputs", []) if (inp.get("widget") or {}).get("name")]
        if isinstance(values, dict):                        # some node packs save their widgets by name
            for k, v in values.items():
                if k not in UI_KEYS:
                    inputs[k] = v
        elif isinstance(values, list) and len(listed) < len([v for v in values if v not in ("fixed", "randomize", "increment", "decrement")]):
            for name, v in zip(widget_order(info, t, values), values):
                if name:
                    inputs[name] = v
        elif isinstance(values, list):
            i = 0
            for inp in n.get("inputs", []):
                w = (inp.get("widget") or {}).get("name")
                if not w:
                    continue
                if i >= len(values):
                    break
                v = values[i]
                i += 1
                if w in names or "." in w:
                    inputs[w] = v
                if _has_control(names.get(w)) and i < len(values) and values[i] in ("fixed", "randomize", "increment", "decrement"):
                    i += 1
        for inp in n.get("inputs", []):
            if inp.get("link") is None:
                continue
            src = upstream(inp["link"])
            key = inp.get("name")
            if src is None:
                inputs.pop(key, None)
                continue
            inputs[key] = [str(src[0]), src[1]]
        graph[str(n["id"])] = {"class_type": t, "inputs": inputs, "_title": n.get("title", "")}

    outputs = [k for k, v in graph.items() if info.get(v["class_type"], {}).get("output_node")]
    keep, todo = set(), list(outputs)
    while todo:
        k = todo.pop()
        if k in keep or k not in graph:
            continue
        keep.add(k)
        todo += [v[0] for v in graph[k]["inputs"].values() if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str)]
    missing = sorted({n["type"] for n in wf["nodes"] if str(n["id"]) in keep and n["type"] not in info})
    if missing:
        raise WorkflowError("the server has no node %s" % ", ".join(missing))
    return {k: v for k, v in graph.items() if k in keep}


def _find(graph, cls, title=None):
    hits = [k for k, v in graph.items() if v["class_type"] == cls and (title is None or title in v.get("_title", ""))]
    return hits


def fill_u22(wf, info, prompt, seconds, images, seed, portrait=True, prefix="film/h3"):
    """The U22 multi-reference workflow with one shot filled in. images: names already uploaded, at
    most 9, in <Picture 1> order. -> graph ready to queue."""
    wf = copy.deepcopy(wf)
    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}
    # the image slots: LoadImage -> SetNode "图像k"
    slots = {}
    for n in wf["nodes"]:
        if n["type"] == "SetNode" and re.fullmatch(r"图像\d+", str((n.get("widgets_values") or [""])[0])):
            k = int(n["widgets_values"][0][2:])
            link = (n.get("inputs") or [{}])[0].get("link")
            if link in links and nodes.get(links[link][1], {}).get("type") == "LoadImage":
                slots[k] = (n, nodes[links[link][1]])
    if len(images) > len(slots):
        raise WorkflowError("U22 takes at most %d reference images; this shot has %d" % (len(slots), len(images)))
    if not images:
        raise WorkflowError("U22 needs at least one reference image")
    for k in sorted(slots):
        setter, loader = slots[k]
        on = k <= len(images)
        setter["mode"] = loader["mode"] = 0 if on else 4
        if on:
            loader["widgets_values"] = [images[k - 1], "image"]
    for n in wf["nodes"]:                                   # no reference videos or audio from us
        if n["type"] in ("VHS_LoadVideo", "LoadAudio"):
            n["mode"] = 4
        if n["type"] == "SetNode" and str((n.get("widgets_values") or [""])[0]).startswith(("参考视频", "参考音频")):
            n["mode"] = 4
    graph = convert(wf, info)

    def one(cls, title=None, what=""):
        hits = _find(graph, cls, title)
        if len(hits) != 1:
            raise WorkflowError("U22: expected one %s%s (%s), found %d" % (cls, " titled %s" % title if title else "", what, len(hits)))
        return graph[hits[0]]["inputs"]

    one("CR Prompt Text", what="the prompt")["prompt"] = prompt
    one("PrimitiveFloat", "时长", "the length in seconds")["value"] = float(seconds)
    one("RandomNoise", what="the seed")["noise_seed"] = int(seed)
    if portrait:
        sel = one("ResolutionSelector", what="the size")
        choices = info["ResolutionSelector"]["input"]["required"]["aspect_ratio"]
        choices = choices[0] if isinstance(choices[0], list) else choices[1].get("options", [])
        upright = next((c for c in choices if c.startswith("9:16")), None)
        if not upright:
            raise WorkflowError("U22: the size node has no 9:16 choice (%s)" % ", ".join(choices))
        sel["aspect_ratio"] = upright
    saved = [k for k in _find(graph, "VHS_VideoCombine") if graph[k]["inputs"].get("save_output")]
    if len(saved) != 1:
        raise WorkflowError("U22: expected one saved video output, found %d" % len(saved))
    graph[saved[0]]["inputs"]["filename_prefix"] = prefix
    for v in graph.values():
        v.pop("_title", None)
    return graph


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    w = json.load(open(sys.argv[1], encoding="utf-8"))
    i = json.load(open(sys.argv[2], encoding="utf-8"))
    g = fill_u22(w, i, "test prompt", 10, ["a.jpg", "b.jpg", "c.jpg", "d.jpg"], 1234)
    for k in sorted(g, key=int):
        print(k, g[k]["class_type"], json.dumps(g[k]["inputs"], ensure_ascii=False)[:230])
