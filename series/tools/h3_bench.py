#!/usr/bin/env python3
"""Benchmark MiniMax H3 against clips we already have from Seedance 2.5.

    python3 h3_bench.py BENCH_DIR --variants base,nostyle,...  [--shots S01,S02] [--seeds 1] [--cap YUAN]
    python3 h3_bench.py BENCH_DIR --sheets                     side-by-side sheets of everything made so far

BENCH_DIR holds bench.json ({shot: {"seconds", "refs": [...], "baseline": "<clip>", "seed": N}}, paths relative
to BENCH_DIR/..; a fixed "seed" makes variants of a shot differ only by their settings), prompts/<shot>.txt (the H3 prompt) and optionally variants.json
({name: {"tuning": {...}, "prompt_suffix": "..."}}). Each take is saved to clips/<shot>.<variant>.<n>.mp4
with a record in results.jsonl (GPU seconds, seed, settings). One rented GPU for the whole run,
given back at the end.
"""
import json
import os
import subprocess
import sys
import time

TOOLS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, TOOLS)
import autodl  # noqa: E402
import comfy  # noqa: E402
import env  # noqa: E402
import h3  # noqa: E402
import film as film_tools  # noqa: E402


class RefHolder:
    """Just enough of a film for h3.ref_addresses: the folder bound to a Jimeng canvas and a place
    to keep the addresses (BENCH_DIR/refs.json)."""
    def __init__(self, project, bench):
        self.project, self.d, self.episode = project, {}, "bench"
        self.state_path = os.path.join(bench, "refs.json")
        self.state = json.load(open(self.state_path, encoding="utf-8")) if os.path.isfile(self.state_path) else {}

    def save_state(self):
        json.dump(self.state, open(self.state_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

VARIANTS = {
    "base": {"tuning": {}},
    "nostyle": {"tuning": {"style_lora": 0}},
    "full": {"tuning": {"style_lora": 0, "turbo": False, "steps": 24, "first_steps": 18}},
    "turbo16": {"tuning": {"style_lora": 0, "steps": 16, "first_steps": 11}},
}


def job_seconds(server, prompt_id):
    job = server.get("/history/" + prompt_id).get(prompt_id, {})
    ts = [m[1].get("timestamp") for m in job.get("status", {}).get("messages", []) if isinstance(m[1], dict) and m[1].get("timestamp")]
    return round((max(ts) - min(ts)) / 1000.0) if ts else None


def sheet(clip, out, seconds, label):
    ff = env.ffmpeg()
    subprocess.run([ff, "-v", "error", "-y", "-i", clip, "-vf", "fps=%s,scale=180:320:force_original_aspect_ratio=decrease,pad=180:320:(ow-iw)/2:(oh-ih)/2,tile=%dx1"
                    % (8.0 / seconds, 8), "-frames:v", "1", out], check=True)


def sheets(bench):
    spec = json.load(open(os.path.join(bench, "bench.json"), encoding="utf-8"))
    root = os.path.dirname(os.path.abspath(bench))
    os.makedirs(os.path.join(bench, "sheets"), exist_ok=True)
    made = sorted(f for f in os.listdir(os.path.join(bench, "clips")) if f.endswith(".mp4"))
    for shot, s in spec.items():
        rows = [("2.5", os.path.join(root, s["baseline"]))] + [(f[len(shot) + 1:-4], os.path.join(bench, "clips", f)) for f in made if f.startswith(shot + ".")]
        parts = []
        for name, clip in rows:
            p = os.path.join(bench, "sheets", "%s.%s.png" % (shot, name))
            sheet(clip, p, s["seconds"], name)
            parts.append(p)
        out = os.path.join(bench, "sheets", shot + ".png")
        args = [env.ffmpeg(), "-v", "error", "-y"]
        for p in parts:
            args += ["-i", p]
        args += ["-filter_complex", "".join("[%d]" % i for i in range(len(parts))) + "vstack=inputs=%d" % len(parts) if len(parts) > 1 else "null", out]
        subprocess.run(args, check=True)
        print("%s: %s (rows: %s)" % (shot, out, ", ".join(n for n, _ in rows)))


def run(bench, names, shots, seeds, cap):
    spec = json.load(open(os.path.join(bench, "bench.json"), encoding="utf-8"))
    extra = os.path.join(bench, "variants.json")
    variants = dict(VARIANTS, **(json.load(open(extra, encoding="utf-8")) if os.path.isfile(extra) else {}))
    root = os.path.dirname(os.path.abspath(bench))
    os.makedirs(os.path.join(bench, "clips"), exist_ok=True)
    log = open(os.path.join(bench, "results.jsonl"), "a", encoding="utf-8")
    holder = RefHolder(root, bench)                     # references go to Jimeng's CDN first; the server fetches them
    paths = sorted({os.path.join(root, r) for shot in (shots or list(spec)) for r in spec[shot]["refs"]})
    print("putting %d reference image(s) on Jimeng's picture CDN" % len(paths), flush=True)
    addresses = dict(zip(paths, h3.ref_addresses(holder, paths, film_tools, log=lambda m: print(m, flush=True))))
    for attempt in range(30):                           # wait for stock: every 2 minutes, up to an hour
        try:
            lease = autodl.up(h3.DEFAULT_APP, "pro6000-p", 8.8, cap, name="h3-bench")
            break
        except autodl.AutoDLError as err:
            if "no stock" not in str(err) or attempt == 29:
                raise
            print("no GPU in stock yet (attempt %d); waiting 2 minutes" % (attempt + 1), flush=True)
            time.sleep(120)
    try:
        server = comfy.Comfy(lease["comfy"])
        server.wait_ready(timeout=900)
        for shot in shots or list(spec):
            s = spec[shot]
            base_prompt = open(os.path.join(bench, "prompts", shot + ".txt"), encoding="utf-8").read()
            for name in names:
                v = variants[name]
                prompt = open(os.path.join(bench, "prompts", v["prompt_file"].replace("{shot}", shot)), encoding="utf-8").read() \
                    if v.get("prompt_file") else base_prompt + v.get("prompt_suffix", "")
                for k in range(seeds):
                    dest = os.path.join(bench, "clips", "%s.%s.%d.mp4" % (shot, name, k + 1))
                    if os.path.exists(dest):
                        continue
                    autodl.touch()
                    print("%s %s take %d" % (shot, name, k + 1), flush=True)
                    try:
                        _, seed, took = server.u22_clip(h3.DEFAULT_WORKFLOW, prompt, s["seconds"], [addresses[os.path.join(root, r)] for r in s["refs"]], dest,
                                                         beat=autodl.touch, tuning=v.get("tuning"), seed=s.get("seed"),
                                                         log=lambda m: print(m, flush=True))
                        hist = server.get("/history?max_items=1")
                        gpu = job_seconds(server, list(hist)[0]) if hist else None
                        rec = {"shot": shot, "variant": name, "take": k + 1, "seed": seed, "wall_s": round(took), "gpu_s": gpu, "tuning": v.get("tuning"), "ok": True}
                    except comfy.ComfyError as err:
                        rec = {"shot": shot, "variant": name, "take": k + 1, "error": str(err)[:300], "ok": False}
                    print("   ", rec, flush=True)
                    log.write(json.dumps(rec, ensure_ascii=False) + "\n")
                    log.flush()
                    if autodl.load() and autodl.cost(autodl.load()) >= cap:
                        print("cap reached")
                        return
    finally:
        autodl.down(why="bench finished")


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        sys.exit(__doc__)

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    if "--sheets" in argv:
        sheets(argv[0])
    else:
        run(argv[0], opt("--variants", "base").split(","), [s for s in (opt("--shots") or "").split(",") if s], int(opt("--seeds", "1")), float(opt("--cap", "12")))
