#!/usr/bin/env python3
"""Talk to a ComfyUI server and run MiniMax H3's reference-to-video workflow on it.

    python3 comfy.py URL info                      version, GPU, and which H3 model files it has
    python3 comfy.py URL run --prompt-file P.txt --seconds 10 --ref a.png --ref b.png --out clip.mp4
                             [--steps 20] [--turbo] [--seed N] [--size 768x1344]   the graph built here
                             [--workflow U22-MiniMaxH3-多参考生视频]                a workflow saved on the server

Used by `film.py draft` when a film's engine is "h3". The graph is the one in ComfyUI's official
template `video_minimax_h3_r2v.json` (read 2026-11-13), built here node by node:

    loaders (video VAE, audio VAE, diffusion model, text encoder)
      -> MiniMaxH3ReferenceToVideo (reference images, prompt, width, height, length)
      -> BasicGuider + BasicScheduler + res_multistep -> SamplerCustomAdvanced
      -> VAEDecode + VAEDecodeAudio -> CreateVideo (24 fps) -> SaveVideo

Facts the builder relies on, from the template and the docs:
  - length is in frames at 24 fps and must be 17k+5; about 15 seconds is the ceiling;
  - width and height are multiples of 32 at about one megapixel (768x1344 upright);
  - there is no negative prompt (the guider runs without one);
  - the turbo LoRA does it in 4 steps instead of 20, at some cost in quality.
Anything the server requires that is not set here is filled in from the server's own defaults
(/object_info), and model file names are chosen from what the server actually has.
"""
import hashlib
import http.client
import json
import mimetypes
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid as uuidlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import env  # noqa: E402

FPS = 24
MAX_SECONDS = 15
UPRIGHT = (768, 1344)
# file-name preferences, best first; the first one the server has is used
WANT = {
    "unet": ("minimax_h3_ref2va_bf16", "minimax_h3_ref2va_int8_convrot", "minimax_h3_ref2va_pruned_bf16",
             "minimax_h3_ref2va_pruned_int8_convrot", "minimax_h3_ref2va_pruned_fp8_scaled", "minimax_h3_ref2va"),
    "clip": ("qwen3vl_32b_minimax_h3_bf16", "qwen3vl_32b_minimax_h3_int8_convrot", "qwen3vl_32b_minimax_h3_nvfp4_awq", "qwen3vl_32b_minimax_h3"),
    "vae": ("minimax_h3_video_vae",),
    "audio_vae": ("minimax_h3_audio_vae",),
    "turbo": ("minimax_h3_ref2v_turbo_4step",),
}


class ComfyError(RuntimeError):
    pass


def frames(seconds):
    """Frames for a clip of this many seconds: the next 17k+5 at or above seconds x 24."""
    f = max(5, int(round(seconds * FPS)))
    return f + (5 - f % 17) % 17


class Comfy:
    def __init__(self, url, timeout=60):
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.client = uuidlib.uuid4().hex
        self._info = {}
        self._saved = {}

    # ---- plain HTTP
    def _open(self, path, data=None, headers=None, timeout=None):
        req = urllib.request.Request(self.url + path, data=data, headers=headers or {})
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as err:
            raise ComfyError("%s: HTTP %s %s" % (path.split("?")[0], err.code, err.read().decode("utf-8", "replace")[:600]))
        except (urllib.error.URLError, OSError) as err:
            raise ComfyError("%s: %s" % (path.split("?")[0], err))

    def _json(self, path, data=None, headers=None, timeout=None):
        """One request and its JSON answer. A link that drops while the answer is being read is a
        ComfyError like any other, never a raw socket error that would end the batch."""
        try:
            with self._open(path, data, headers, timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (OSError, http.client.HTTPException, ValueError) as err:
            raise ComfyError("%s: %s" % (path.split("?")[0], err))

    def get(self, path):
        return self._json(path)

    def post(self, path, body):
        return self._json(path, json.dumps(body).encode("utf-8"), {"Content-Type": "application/json"})

    # ---- the server
    def wait_ready(self, timeout=600, log=print):
        deadline, said = time.time() + timeout, False
        while True:
            try:
                return self.get("/system_stats")
            except (ComfyError, ValueError):
                if time.time() > deadline:
                    raise ComfyError("ComfyUI at %s did not answer within %d s" % (self.url, timeout))
                if not said:
                    log("waiting for ComfyUI to come up")
                    said = True
                time.sleep(6)

    def node(self, class_type):
        if class_type not in self._info:
            for attempt in range(4):                    # the link to a rented server drops requests now and then
                try:
                    self._info[class_type] = self.get("/object_info/" + urllib.parse.quote(class_type)).get(class_type)
                    break
                except (ComfyError, ValueError):
                    if attempt == 3:
                        raise
                    time.sleep(3)
        if not self._info[class_type]:
            raise ComfyError("this ComfyUI has no node %s (too old, or MiniMax H3 support is missing)" % class_type)
        return self._info[class_type]

    def choices(self, class_type, field):
        spec = self.node(class_type)["input"].get("required", {}).get(field) or self.node(class_type)["input"].get("optional", {}).get(field)
        if not spec:
            return []
        first = spec[0]
        if isinstance(first, list):
            return first
        return (spec[1] or {}).get("options", []) if len(spec) > 1 and isinstance(spec[1], dict) else []

    def pick(self, class_type, field, wanted):
        have = self.choices(class_type, field)
        for want in wanted:
            for name in have:
                if os.path.basename(name).startswith(want):
                    return name
        raise ComfyError("no file for %s on the server (looked for %s among %d %s files)" % (wanted[0], ", ".join(wanted), len(have), field))

    def upload(self, path, tries=4):
        """-> the name ComfyUI gave the image (for a LoadImage node). The picture is sent as a JPEG no
        larger than 1024 pixels a side: the link to a rented server is slow, and the model resizes
        its references anyway."""
        send, temp = path, None
        ffmpeg = env.ffmpeg()
        if os.path.getsize(path) > 600 * 1024 and (os.path.isfile(ffmpeg) or shutil.which(ffmpeg)):
            temp = os.path.join(tempfile.mkdtemp(prefix="comfy-up-"), os.path.splitext(os.path.basename(path))[0] + ".jpg")
            done = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", path, "-vf",
                                   "scale='min(1024,iw)':'min(1024,ih)':force_original_aspect_ratio=decrease", "-q:v", "3", temp])
            send = temp if done.returncode == 0 and os.path.isfile(temp) else path
        boundary = "----film" + uuidlib.uuid4().hex
        name = "film_%s_%s" % (hashlib.sha1(os.path.abspath(path).encode("utf-8")).hexdigest()[:10], "ref" + os.path.splitext(send)[1])
        kind = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with open(send, "rb") as handle:
            blob = handle.read()
        parts = [("--%s\r\nContent-Disposition: form-data; name=\"image\"; filename=\"%s\"\r\nContent-Type: %s\r\n\r\n"
                  % (boundary, name, kind)).encode("utf-8"), blob,
                 ("\r\n--%s\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n--%s--\r\n" % (boundary, boundary)).encode("utf-8")]
        try:
            for attempt in range(tries):
                try:
                    with self._open("/upload/image", b"".join(parts), {"Content-Type": "multipart/form-data; boundary=" + boundary}, timeout=240) as resp:
                        answer = json.loads(resp.read().decode("utf-8"))
                    return (answer.get("subfolder") + "/" if answer.get("subfolder") else "") + answer["name"]
                except (ComfyError, OSError, ValueError) as err:
                    if attempt + 1 == tries:
                        raise ComfyError("could not upload %s (%d KB) after %d tries: %s" % (os.path.basename(path), len(blob) // 1024, tries, err))
                    time.sleep(4)
        finally:
            if temp:
                shutil.rmtree(os.path.dirname(temp), ignore_errors=True)

    def fill_defaults(self, graph):
        """Give every required input the server's default when the graph leaves it out. A dynamic
        choice (SaveVideo's format, for one) takes its first option, and that option's own required
        inputs are filled the same way under dotted names (format.codec)."""
        def fill(inputs, field, spec, prefix=""):
            name = prefix + field
            options = spec[1].get("options") if len(spec) > 1 and isinstance(spec[1], dict) else None
            if spec[0] == "COMFY_DYNAMICCOMBO_V3" and options:
                chosen = next((o for o in options if o.get("key") == inputs.get(name)), options[0])
                inputs.setdefault(name, chosen.get("key"))
                for sub, sub_spec in (chosen.get("inputs", {}).get("required") or {}).items():
                    fill(inputs, sub, sub_spec, name + ".")
            elif name in inputs:
                return
            elif isinstance(spec[0], list):
                if spec[0]:
                    inputs[name] = spec[0][0]
            elif len(spec) > 1 and isinstance(spec[1], dict) and "default" in spec[1]:
                inputs[name] = spec[1]["default"]
            elif options:
                inputs[name] = options[0]

        for node in graph.values():
            for field, spec in self.node(node["class_type"])["input"].get("required", {}).items():
                fill(node["inputs"], field, spec)
        return graph

    def queued_by_us(self):
        """-> prompt ids this client has waiting, running or finished on the server. Raises
        ComfyError when the server cannot be asked: an unanswered lookup is not "nothing there"."""
        ids = []
        q = self.get("/queue")
        for item in q.get("queue_running", []) + q.get("queue_pending", []):
            if len(item) > 3 and isinstance(item[3], dict) and item[3].get("client_id") == self.client:
                ids.append(item[1])
        for pid, job in self.get("/history?max_items=20").items():
            extra = (job.get("prompt") or [None] * 4)
            if len(extra) > 3 and isinstance(extra[3], dict) and extra[3].get("client_id") == self.client:
                ids.append(pid)
        return ids

    def known(self, prompt_id):
        """-> True when the server has this job (waiting, running or finished). Raises ComfyError
        when it cannot be asked."""
        if self.get("/history/" + prompt_id).get(prompt_id):
            return True
        q = self.get("/queue")
        return any(len(item) > 1 and item[1] == prompt_id for item in q.get("queue_running", []) + q.get("queue_pending", []))

    def queue(self, graph, tries=3):
        """Send the job once. The job carries an id made here, so after a dropped reply the runner
        asks for exactly that id before sending again, and sends again only when the server has
        answered that it does not have it. A job is never queued twice, and never mistaken for an
        earlier one."""
        prompt_id = str(uuidlib.uuid4())
        body = json.dumps({"prompt": graph, "client_id": self.client, "prompt_id": prompt_id},
                          ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        try:
            before = set(self.queued_by_us())               # for a server too old to take our id
        except ComfyError:
            before = None
        for attempt in range(tries):
            try:
                answer = self._json("/prompt", body, {"Content-Type": "application/json"}, timeout=300)
                break
            except ComfyError as err:
                if "HTTP 4" in str(err):
                    raise ComfyError("the server refused the workflow: %s" % err)
                for look in range(8):                       # did it arrive? ask until the server answers
                    time.sleep(5 + 5 * look)
                    try:
                        if self.known(prompt_id):
                            return prompt_id
                        landed = [pid for pid in self.queued_by_us() if before is not None and pid not in before]
                        if landed:
                            return landed[0]
                        if before is None:
                            raise ComfyError("cannot tell an old server's new job from earlier ones")
                        break                               # the server says it does not have it: safe to send again
                    except ComfyError as look_err:
                        if look == 7 or "old server" in str(look_err):
                            raise ComfyError("the workflow was sent but the server could not be asked whether it arrived; "
                                             "not sending it again (%s)" % err)
                if attempt + 1 == tries:
                    raise ComfyError("could not send the workflow after %d tries: %s" % (tries, err))
        if answer.get("node_errors"):
            raise ComfyError("the server refused the workflow: %s" % json.dumps(answer["node_errors"], ensure_ascii=False)[:600])
        return answer.get("prompt_id") or prompt_id

    def wait(self, prompt_id, timeout=3600, beat=None):
        """-> the output files of a finished job, as ComfyUI describes them."""
        deadline, misses, gone_since, polls = time.time() + timeout, 0, None, 0
        while time.time() < deadline:
            try:                                        # a rented link drops a request now and then; the job runs on
                job = self.get("/history/" + prompt_id).get(prompt_id)
                misses = 0
            except ComfyError:
                misses += 1
                if misses >= 20:
                    raise
                time.sleep(5)
                continue
            if job:
                state = job.get("status", {})
                if state.get("status_str") == "error":
                    notes = [m[1] for m in state.get("messages", []) if m and m[0] == "execution_error"]
                    raise ComfyError("generation failed: %s" % json.dumps(notes[-1] if notes else state, ensure_ascii=False)[:500])
                if state.get("completed", True) and job.get("outputs"):
                    return [f for out in job["outputs"].values() for group in out.values() if isinstance(group, list)
                            for f in group if isinstance(f, dict) and f.get("filename")]
                if state.get("completed") and state.get("status_str") == "success":
                    raise ComfyError("the job finished with no output")
            else:
                polls += 1
                if polls % 6 == 0:                      # every half minute: is it still waiting or running at all?
                    try:
                        q = self.get("/queue")
                        there = any(len(i) > 1 and i[1] == prompt_id for i in q.get("queue_running", []) + q.get("queue_pending", []))
                        gone_since = None if there else (gone_since or time.time())
                    except ComfyError:
                        pass
                    if gone_since and time.time() - gone_since > 90:
                        raise ComfyError("the job is gone from the server (neither queued, running nor finished); "
                                         "the server may have restarted")
            if beat:
                beat()
            time.sleep(5)
        raise ComfyError("no result after %d s; the job may still be running on the server" % timeout)

    def download(self, entry, dest, tries=10):
        """Save an output file. A rented server's link can drop mid-file: each retry asks for the
        rest of the file (an HTTP range) instead of starting over."""
        query = urllib.parse.urlencode({"filename": entry["filename"], "subfolder": entry.get("subfolder", ""), "type": entry.get("type", "output")})
        part = dest + ".part"
        if os.path.exists(part):
            os.remove(part)
        for attempt in range(tries):
            have = os.path.getsize(part) if os.path.exists(part) else 0
            try:
                with self._open("/view?" + query, headers={"Range": "bytes=%d-" % have} if have else None, timeout=600) as resp:
                    if have and resp.status != 206:             # the server ignored the range: start again
                        have = 0
                    total = resp.headers.get("Content-Length")
                    total = have + int(total) if total and total.isdigit() else None
                    with open(part, "ab" if have else "wb") as out:
                        while True:
                            chunk = resp.read(1 << 16)
                            if not chunk:
                                break
                            out.write(chunk)
                if total is None or os.path.getsize(part) >= total:
                    os.replace(part, dest)
                    return dest
            except (ComfyError, OSError, http.client.HTTPException) as err:
                if have and "HTTP 416" in str(err):         # the whole file had arrived before the link dropped
                    os.replace(part, dest)
                    return dest
                if attempt + 1 == tries:
                    raise ComfyError("could not download %s after %d tries: %s" % (entry["filename"], tries, err))
            time.sleep(min(30, 3 * (attempt + 1)))
        raise ComfyError("could not download %s whole after %d tries" % (entry["filename"], tries))

    # ---- MiniMax H3, reference to video
    def h3_models(self):
        return {"unet": self.pick("UNETLoader", "unet_name", WANT["unet"]), "clip": self.pick("CLIPLoader", "clip_name", WANT["clip"]),
                "vae": self.pick("VAELoader", "vae_name", WANT["vae"]), "audio_vae": self.pick("VAELoader", "vae_name", WANT["audio_vae"])}

    def h3_graph(self, prompt, seconds, images, size=UPRIGHT, steps=20, turbo=False, seed=None, prefix="film/h3"):
        """images: names already uploaded, in <Picture 1>, <Picture 2>, ... order."""
        if seconds > MAX_SECONDS:
            raise ComfyError("MiniMax H3 clips run to about %d seconds; this one asks for %s" % (MAX_SECONDS, seconds))
        files = self.h3_models()
        ref_slots = [k for group in ("required", "optional") for k in self.node("MiniMaxH3ReferenceToVideo")["input"].get(group, {})
                     if k.startswith("ref_images")]
        g = {
            "1": {"class_type": "VAELoader", "inputs": {"vae_name": files["vae"]}},
            "2": {"class_type": "VAELoader", "inputs": {"vae_name": files["audio_vae"]}},
            "3": {"class_type": "UNETLoader", "inputs": {"unet_name": files["unet"]}},
            "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": files["clip"], "type": "minimax"}},
            "20": {"class_type": "MiniMaxH3ReferenceToVideo",
                   "inputs": {"clip": ["4", 0], "vae": ["1", 0], "audio_vae": ["2", 0], "prompt": prompt,
                              "width": size[0], "height": size[1], "length": frames(seconds)}},
            "21": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed if seed is not None else random.randrange(1 << 48)}},
            "22": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
            "23": {"class_type": "BasicScheduler", "inputs": {"model": ["3", 0], "scheduler": "simple", "steps": 4 if turbo else steps, "denoise": 1.0}},
            "24": {"class_type": "BasicGuider", "inputs": {"model": ["3", 0], "conditioning": ["20", 0]}},
            "25": {"class_type": "SamplerCustomAdvanced",
                   "inputs": {"noise": ["21", 0], "guider": ["24", 0], "sampler": ["22", 0], "sigmas": ["23", 0], "latent_image": ["20", 1]}},
            "26": {"class_type": "VAEDecode", "inputs": {"samples": ["25", 0], "vae": ["1", 0]}},
            "27": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["25", 0], "vae": ["2", 0]}},
            "28": {"class_type": "CreateVideo", "inputs": {"images": ["26", 0], "audio": ["27", 0], "fps": FPS}},
            "29": {"class_type": "SaveVideo", "inputs": {"video": ["28", 0], "filename_prefix": prefix}},
        }
        if turbo:
            g["5"] = {"class_type": "LoraLoaderModelOnly",
                      "inputs": {"model": ["3", 0], "lora_name": self.pick("LoraLoaderModelOnly", "lora_name", WANT["turbo"]), "strength_model": 1.0}}
            g["24"]["inputs"]["model"] = ["5", 0]
        for i, name in enumerate(images):
            g[str(100 + i)] = {"class_type": "LoadImage", "inputs": {"image": name}}
            g["20"]["inputs"]["ref_images.ref_image_%d" % i] = [str(100 + i), 0]
        if ref_slots and not any(s.endswith("ref_image_0") or s == "ref_images" for s in ref_slots):
            raise ComfyError("this server's MiniMaxH3ReferenceToVideo takes reference images under %s, not ref_images.ref_image_N" % ref_slots)
        return self.fill_defaults(g)

    # ---- a workflow saved on the server (the default: U22 of autodl.art app 252)
    def saved_workflows(self):
        return self.get("/api/userdata?dir=workflows&recurse=true")

    def saved_workflow(self, wanted):
        """wanted: a file name, or its start ("U22-MiniMaxH3-多参考生视频"). -> (path, workflow).
        Kept after the first fetch: one server, one copy."""
        if wanted in self._saved:
            return self._saved[wanted]
        self._saved[wanted] = self._fetch_workflow(wanted)
        return self._saved[wanted]

    def _fetch_workflow(self, wanted):
        names = self.saved_workflows()
        hits = [n for n in names if os.path.basename(n) == wanted or os.path.basename(n).startswith(wanted)]
        if len(hits) != 1:
            raise ComfyError("expected one saved workflow matching %r on the server, found %d%s" % (
                wanted, len(hits), (": " + ", ".join(hits)) if hits else ""))
        with self._open("/api/userdata/" + urllib.parse.quote("workflows/" + hits[0], safe=""), timeout=120) as resp:
            return hits[0], json.loads(resp.read().decode("utf-8"))

    def info_for(self, wf):
        classes = {n["type"] for n in wf.get("nodes", [])}
        out = {}
        import comfy_workflow
        for cls in classes - comfy_workflow.EDITOR_ONLY:
            try:
                out[cls] = self.node(cls)
            except ComfyError as err:
                if "has no node" not in str(err):
                    raise
        return out

    # ---- a copy of the saved workflow and its node definitions, kept between rentals (the link is slow)
    def _kept_path(self, workflow):
        home = os.environ.get("JIMENG_SERIES_HOME") or os.path.expanduser("~/.config/jimeng-series")
        return os.path.join(home, "comfy-cache", hashlib.sha1(workflow.encode("utf-8")).hexdigest()[:16] + ".json")

    def _kept(self, workflow):
        try:
            with open(self._kept_path(workflow), encoding="utf-8") as handle:
                kept = json.load(handle)
            return kept if kept.get("workflow") and kept.get("info") else None
        except (OSError, ValueError):
            return None

    def _keep(self, workflow, path, wf, info):
        target = self._kept_path(workflow)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            json.dump({"path": path, "workflow": wf, "info": info, "saved": time.time()}, handle, ensure_ascii=False)

    def _forget(self, workflow):
        try:
            os.remove(self._kept_path(workflow))
        except OSError:
            pass
        self._saved.pop(workflow, None)


    def u22_clip(self, workflow, prompt, seconds, image_paths, dest, beat=None, log=print, seed=None, tuning=None):
        """Run the saved U22 workflow for one shot. -> (dest, seed, seconds it took)."""
        import comfy_workflow
        started = time.time()
        tick = beat or (lambda: None)                   # the setup can take minutes over a rented link: keep the GPU marked busy
        kept = self._kept(workflow)                     # the workflow and its node definitions, from an earlier rental
        path, wf = (kept["path"], kept["workflow"]) if kept else self.saved_workflow(workflow)
        if kept:
            self._info.update(kept["info"])
        tick()
        marks = [("start", started)]
        names = []
        for p in image_paths:                           # an address (CDN link, file on the server) is fetched by the server
            names.append(p if comfy_workflow.is_address(p) else self.upload(p))
            tick()
        seed = seed if seed is not None else random.randrange(1 << 48)
        info = self.info_for(wf)
        if any(comfy_workflow.is_address(n) for n in names):
            info["LoadImageFromUrl"] = self.node("LoadImageFromUrl")
        tick()
        if not kept:
            self._keep(workflow, path, wf, info)
        marks.append(("setup", time.time()))
        try:
            graph = comfy_workflow.fill_u22(wf, info, prompt, seconds, names, seed, tuning=tuning)
        except comfy_workflow.WorkflowError as err:
            raise ComfyError(str(err))
        for attempt in range(8):
            try:
                job = self.queue(graph)
            except ComfyError as err:
                if not kept or "refused the workflow" not in str(err):
                    raise
                log("  the kept copy of the workflow no longer fits this server; fetching it again")
                self._forget(workflow)
                return self.u22_clip(workflow, prompt, seconds, image_paths, dest, beat, log, seed, tuning)
            log("  queued %s on %s: %d reference image(s), %s s" % (job[:8], os.path.basename(path), len(names), seconds))
            marks.append(("send", time.time()))
            try:
                files = self.wait(job, beat=beat)
                marks.append(("render", time.time()))
                break
            except ComfyError as err:                   # the URL loader gives a slow CDN only 5 s; what it did fetch stays
                if "LoadImageFromUrl" not in str(err) or "timed out" not in str(err) or attempt == 7:
                    raise                               # cached on the server, so sending again fetches only the rest
                log("  a reference was slow to fetch; sending again (nothing was generated)")
                tick()
        videos = [f for f in files if f["filename"].lower().endswith((".mp4", ".webm", ".mov", ".mkv")) and f.get("type") == "output"]
        if not videos:
            raise ComfyError("the job finished without a saved video file")
        self.download(videos[-1], dest)
        marks.append(("download", time.time()))
        log("  timing: " + ", ".join("%s %.0f s" % (marks[i][0], marks[i][1] - marks[i - 1][1]) for i in range(1, len(marks))))
        return dest, seed, time.time() - started

    def h3_clip(self, prompt, seconds, image_paths, dest, beat=None, log=print, **options):
        """Upload the references, run the workflow, save the clip. -> (dest, seed, seconds it took)."""
        started = time.time()
        names = []
        for p in image_paths:
            names.append(self.upload(p))
            if beat:
                beat()
        graph = self.h3_graph(prompt, seconds, names, **options)
        job = self.queue(graph)
        log("  queued %s: %d frames, %d reference image(s), %d steps" % (job[:8], graph["20"]["inputs"]["length"], len(names), graph["23"]["inputs"]["steps"]))
        videos = [f for f in self.wait(job, beat=beat) if f["filename"].lower().endswith((".mp4", ".webm", ".mov", ".mkv"))]
        if not videos:
            raise ComfyError("the job finished without a video file")
        self.download(videos[-1], dest)
        return dest, graph["21"]["inputs"]["noise_seed"], time.time() - started


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        sys.exit(__doc__)
    server, cmd = Comfy(argv[0]), argv[1]

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    try:
        if cmd == "info":
            stats = server.wait_ready(timeout=30)
            print("ComfyUI %s; %s" % (stats.get("system", {}).get("comfyui_version"),
                                      "; ".join("%s %.0f GB" % (d.get("name"), d.get("vram_total", 0) / 2 ** 30) for d in stats.get("devices", []))))
            for kind, name in server.h3_models().items():
                print("  %-9s %s" % (kind, name))
            print("  reference inputs: %s" % ", ".join(k for group in ("required", "optional")
                                                       for k in server.node("MiniMaxH3ReferenceToVideo")["input"].get(group, {}) if k.startswith("ref_")))
        elif cmd == "run":
            refs = [argv[i + 1] for i, a in enumerate(argv) if a == "--ref"]
            size = tuple(int(v) for v in opt("--size", "%dx%d" % UPRIGHT).split("x"))
            prompt = open(opt("--prompt-file"), encoding="utf-8").read()
            try:                                        # a rented GPU must not look idle while it works
                import autodl
                beat = autodl.touch
            except ImportError:
                beat = None
            if opt("--workflow"):
                dest, seed, took = server.u22_clip(opt("--workflow"), prompt, float(opt("--seconds", "5")), refs, opt("--out", "h3.mp4"),
                                                   beat=beat, seed=int(opt("--seed")) if opt("--seed") else None)
            else:
                dest, seed, took = server.h3_clip(prompt, float(opt("--seconds", "5")), refs, opt("--out", "h3.mp4"), beat=beat, size=size,
                                                  steps=int(opt("--steps", "20")), turbo="--turbo" in argv,
                                                  seed=int(opt("--seed")) if opt("--seed") else None)
            print("wrote %s (seed %d) in %.0f s" % (dest, seed, took))
        else:
            sys.exit(__doc__)
    except ComfyError as err:
        sys.exit("comfy: %s" % err)


if __name__ == "__main__":
    main()
