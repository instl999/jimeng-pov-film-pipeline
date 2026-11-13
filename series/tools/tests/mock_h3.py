#!/usr/bin/env python3
"""Local stand-ins for the AutoDL Art instance API and a ComfyUI server with MiniMax H3, for
rehearsing `film.py draft --run` on the H3 engine without renting anything.

    python3 mock_h3.py PORT CLIP.mp4 [LOG.jsonl]

Serves both on 127.0.0.1:PORT. Every request is appended to LOG.jsonl so a test can check what was
sent. The "instance" starts on the third status poll; a "generation" finishes on the second history
poll and hands back CLIP.mp4 whatever was asked for.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT, CLIP = int(sys.argv[1]), sys.argv[2]
LOG = sys.argv[3] if len(sys.argv) > 3 else None
S = {"instance": None, "polls": 0, "state": "none", "jobs": {}, "uploads": []}

COMBO = lambda *names: [list(names)]                    # noqa: E731
NODES = {
    "VAELoader": {"required": {"vae_name": COMBO("minimax_h3_video_vae_int8_convrot.safetensors", "minimax_h3_audio_vae_fp32.safetensors", "ae.safetensors")}},
    "UNETLoader": {"required": {"unet_name": COMBO("flux1-dev.safetensors", "minimax_h3_ref2va_pruned_int8_convrot.safetensors", "minimax_h3_fl2va_pruned_int8_convrot.safetensors"),
                                "weight_dtype": COMBO("default", "fp8_e4m3fn")}},
    "CLIPLoader": {"required": {"clip_name": COMBO("qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"), "type": COMBO("stable_diffusion", "minimax")},
                   "optional": {"device": COMBO("default", "cpu")}},
    "LoraLoaderModelOnly": {"required": {"model": ["MODEL"], "lora_name": COMBO("minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"),
                                         "strength_model": ["FLOAT", {"default": 1.0}]}},
    "MiniMaxH3ReferenceToVideo": {"required": {"clip": ["CLIP"], "vae": ["VAE"], "audio_vae": ["VAE"], "prompt": ["STRING", {"multiline": True}],
                                               "width": ["INT", {"default": 1344}], "height": ["INT", {"default": 768}],
                                               "length": ["INT", {"default": 124}], "resize_mode": COMBO("match", "crop")},
                                  "optional": {"ref_images.ref_image_0": ["IMAGE"], "ref_videos.ref_video_0": ["IMAGE"], "ref_audios.ref_audio_0": ["AUDIO"]}},
    "RandomNoise": {"required": {"noise_seed": ["INT", {"default": 0}]}},
    "KSamplerSelect": {"required": {"sampler_name": COMBO("euler", "res_multistep")}},
    "BasicScheduler": {"required": {"model": ["MODEL"], "scheduler": COMBO("simple"), "steps": ["INT", {"default": 20}], "denoise": ["FLOAT", {"default": 1.0}]}},
    "BasicGuider": {"required": {"model": ["MODEL"], "conditioning": ["CONDITIONING"]}},
    "SamplerCustomAdvanced": {"required": {"noise": ["NOISE"], "guider": ["GUIDER"], "sampler": ["SAMPLER"], "sigmas": ["SIGMAS"], "latent_image": ["LATENT"]}},
    "VAEDecode": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}},
    "VAEDecodeAudio": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}},
    "CreateVideo": {"required": {"images": ["IMAGE"], "fps": ["FLOAT", {"default": 30.0}], "bit_depth": ["INT", {"default": 8}]}, "optional": {"audio": ["AUDIO"]}},
    "SaveVideo": {"required": {"video": ["VIDEO"], "filename_prefix": ["STRING", {"default": "video/ComfyUI"}], "format": COMBO("auto", "mp4"), "codec": COMBO("auto", "h264")}},
    "LoadImage": {"required": {"image": COMBO("example.png")}},
}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def answer(self, body, code=200, kind="application/json"):
        blob = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(blob)))
        self.end_headers()
        self.wfile.write(blob)

    def record(self, body):
        if LOG:
            with open(LOG, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"method": self.command, "path": self.path, "auth": bool(self.headers.get("Authorization")),
                                         "body": body if isinstance(body, (dict, list)) else None}, ensure_ascii=False) + "\n")

    def handle_any(self):
        size = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(size) if size else b""
        try:
            body = json.loads(raw.decode("utf-8")) if raw and "json" in (self.headers.get("Content-Type") or "") else None
        except ValueError:
            body = None
        self.record(body)
        url = urlparse(self.path)
        path = url.path
        ok = lambda data=None: self.answer({"code": "Success", "data": data, "msg": "", "request_id": "mock"})    # noqa: E731
        # ---- AutoDL Art
        if path.startswith("/api/v1/adl_dev/"):
            if not self.headers.get("Authorization"):
                return self.answer({"code": "AuthorizeFailed", "data": None, "msg": "no token"})
            name = path.rsplit("/", 1)[-1]
            if name == "create":
                S.update(instance="pro-mock0001", polls=0, state="starting")
                return ok(S["instance"])
            if name == "status":
                if S["state"] == "starting":
                    S["polls"] += 1
                    if S["polls"] >= 3:
                        S["state"] = "running"
                return ok(S["state"])
            if name == "snapshot":
                return ok({"service_6006_domain": "127.0.0.1:%d" % PORT, "service_6006_port_protocol": "http", "payg_price": 8800})
            if name == "power_off":
                S["state"] = "shutdown"
                return ok()
            if name == "release":
                if S["state"] != "shutdown":
                    return self.answer({"code": "Failed", "data": None, "msg": "power off first"})
                S.update(instance=None, state="none")
                return ok()
            if name == "list":
                return ok({"list": [{"uuid": S["instance"], "status": S["state"]}] if S["instance"] else [], "result_total": 1 if S["instance"] else 0})
            return self.answer({"code": "NotFound", "data": None, "msg": path})
        # ---- ComfyUI (only while the "instance" runs)
        if S["state"] != "running":
            return self.answer(b"instance is not running", 502, "text/plain")
        if path == "/system_stats":
            return self.answer({"system": {"comfyui_version": "0.38.1-mock"}, "devices": [{"name": "cuda:0 MOCK", "vram_total": 96 * 2 ** 30}]})
        if path.startswith("/object_info/"):
            cls = path.rsplit("/", 1)[-1]
            return self.answer({cls: {"input": NODES[cls]}} if cls in NODES else {})
        if path == "/upload/image":
            S["uploads"].append(len(raw))
            return self.answer({"name": "ref_%d.png" % len(S["uploads"]), "subfolder": "", "type": "input"})
        if path == "/prompt":
            graph = (body or {}).get("prompt", {})
            errors = {}
            for nid, node in graph.items():
                spec = NODES.get(node.get("class_type"))
                if spec is None:
                    errors[nid] = "unknown node %s" % node.get("class_type")
                    continue
                missing = [k for k in spec.get("required", {}) if k not in node.get("inputs", {})]
                if missing:
                    errors[nid] = "missing %s" % ", ".join(missing)
            if errors:
                return self.answer({"error": "validation", "node_errors": errors}, 400)
            job = "job-%04d" % (len(S["jobs"]) + 1)
            S["jobs"][job] = 0
            return self.answer({"prompt_id": job, "number": len(S["jobs"]), "node_errors": {}})
        if path.startswith("/history/"):
            job = path.rsplit("/", 1)[-1]
            if job not in S["jobs"]:
                return self.answer({})
            S["jobs"][job] += 1
            if S["jobs"][job] < 2:
                return self.answer({})
            return self.answer({job: {"status": {"status_str": "success", "completed": True, "messages": []},
                                      "outputs": {"29": {"images": [{"filename": "h3_00001_.mp4", "subfolder": "film", "type": "output"}], "animated": [True]}}}})
        if path == "/view":
            if "filename" not in parse_qs(url.query):
                return self.answer(b"no filename", 400, "text/plain")
            return self.answer(open(CLIP, "rb").read(), kind="video/mp4")
        return self.answer(b"not found", 404, "text/plain")

    do_GET = do_POST = handle_any


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
