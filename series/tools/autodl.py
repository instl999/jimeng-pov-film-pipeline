#!/usr/bin/env python3
"""Rent, use and give back a cloud GPU on AutoDL Art (https://www.autodl.art), for ComfyUI work.

    python3 autodl.py list                      instances on the account (read-only)
    python3 autodl.py status                    the instance this machine is holding, if any
    python3 autodl.py up --app UUID --gpu SPEC --price YUAN_PER_HOUR --cap YUAN [--name NAME]
                                                create an instance, wait until it runs, print its ComfyUI address
    python3 autodl.py down                      power off, then release (billing ends)
    python3 autodl.py sweep                     give the instance back if it has been idle 15 minutes

The token is read from the file ~/.config/jimeng-series/autodl.token (or the variable AUTODL_TOKEN).
It is sent only to the API host, in the Authorization header, and is never printed.

Rules built in (a GPU that will not be needed for 15 minutes is powered off and released):
  - an instance is never created without a price and a cap in yuan; when the running cost reaches
    the cap the instance is given back;
  - `up` starts a small watchdog process on this machine that gives the instance back after 15
    idle minutes, or at the cap, even if the program that asked for it has died;
  - giving back means power off and then release: a powered-off instance still bills for its disk;
  - one instance at a time.
State is in ~/.config/jimeng-series/autodl.state.json, a line per rental in autodl.ledger.jsonl.

API reference: https://www.autodl.art/docs/app_api/ (read 2026-11-13).
"""
import contextlib
import fcntl
import http.client
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = os.environ.get("AUTODL_API", "https://www.autodl.art").rstrip("/")
HOME = os.environ.get("JIMENG_SERIES_HOME") or os.path.expanduser("~/.config/jimeng-series")   # the variable is for tests
STATE, LEDGER, TOKEN_FILE = (os.path.join(HOME, n) for n in ("autodl.state.json", "autodl.ledger.jsonl", "autodl.token"))
LOCK, WATCHDOG_PID = STATE + ".lock", STATE + ".watchdog"
IDLE_LIMIT = 15 * 60
# GPU types that run app 252's U22 (it needs well over 32 GB), cheapest first after the tested one;
# list prices in yuan an hour on 2026-11-13. Used in order when the first has no stock.
FALLBACK_GPUS = [("pro6000-p", 8.8), ("6000d", 6.8), ("pro5000", 5.56), ("h800", 10.5)]
BOOT_TIMEOUT = 15 * 60


class AutoDLError(RuntimeError):
    pass


def token():
    value = os.environ.get("AUTODL_TOKEN", "").strip()
    if not value and os.path.isfile(TOKEN_FILE):
        value = open(TOKEN_FILE, encoding="utf-8").read().strip()
    if not value:
        raise AutoDLError("no AutoDL token: put it in %s (mode 600)" % TOKEN_FILE)
    return value


def call(method, path, body=None, timeout=40):
    """One API call. -> the "data" of the answer. A GET takes its parameters in the query string: the docs
    show them as a body, but the live API answers RequestParameterIsWrong to that (checked 2026-11-13)."""
    data = None if method == "GET" else json.dumps(body or {}).encode("utf-8")
    if method == "GET" and body:
        path += "?" + urllib.parse.urlencode(body)
    req = urllib.request.Request(API + path, data=data, method=method,
                                 headers={"Authorization": token(), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            answer = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        raise AutoDLError("%s %s: HTTP %s %s" % (method, path, err.code, err.read().decode("utf-8", "replace")[:200]))
    except (urllib.error.URLError, OSError, ValueError, http.client.HTTPException) as err:
        raise AutoDLError("%s %s: %s" % (method, path, err))
    if answer.get("code") != "Success":
        raise AutoDLError("%s %s: %s %s" % (method, path, answer.get("code"), answer.get("msg")))
    return answer.get("data")


# ---- the API, one function per documented call
def list_instances():
    data = call("POST", "/api/v1/adl_dev/dev/instance/pro/list", {"page_index": 1, "page_size": 50}) or {}
    return data.get("list") or []


def create(app_uuid, gpu_spec, name, version="latest", disk_gb=0):
    body = {"req_gpu_amount": 1, "expand_system_disk_by_gb": disk_gb, "gpu_spec_uuid": gpu_spec,
            "application_uuid": app_uuid, "application_version": version, "instance_name": name}
    region = os.environ.get("AUTODL_REGION")             # westDC3 (north-west) or beijingDC2; default: AutoDL picks
    if region:
        body["data_center_list"] = [region]
    return call("POST", "/api/v1/adl_dev/dev/instance/pro/create", body, timeout=90)


def status(uuid):
    return call("GET", "/api/v1/adl_dev/dev/instance/pro/status", {"instance_uuid": uuid})


def snapshot(uuid):
    return call("GET", "/api/v1/adl_dev/dev/instance/pro/snapshot", {"instance_uuid": uuid}) or {}


def power_off(uuid):
    return call("POST", "/api/v1/adl_dev/dev/instance/pro/power_off", {"instance_uuid": uuid})


def release(uuid):
    return call("POST", "/api/v1/adl_dev/dev/instance/pro/release", {"instance_uuid": uuid})


# ---- the one instance this machine holds
@contextlib.contextmanager
def locked():
    """Every change to the state file happens under this lock, so a heartbeat, a give-back and a
    second program can never undo each other."""
    os.makedirs(HOME, exist_ok=True)
    with open(LOCK, "a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def alive(pid):
    try:
        os.kill(int(pid), 0)
        return True
    except (OSError, TypeError, ValueError):
        return False


def load():
    if os.path.isfile(STATE):
        with open(STATE, encoding="utf-8") as handle:
            return json.load(handle)
    return None


def save(state):
    os.makedirs(HOME, exist_ok=True)
    tmp = STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, ensure_ascii=False, indent=1)
    os.replace(tmp, STATE)


def cost(state, now=None):
    """Yuan so far, from the time it was created and its hourly price."""
    return round(((now or time.time()) - state["created"]) / 3600.0 * state["price"], 2)


def touch():
    """Say the instance is in use now; the idle clock starts again. Never brings back a state that
    was given back meanwhile."""
    with locked():
        state = load()
        if state and state.get("uuid"):
            state["last_used"] = time.time()
            save(state)


LAST = {}          # the rental this process created last, even when it failed to start (for the film's spend)


def adopt_orphan(name, log=print):
    """After a create whose answer was lost: find an instance made under our one-off name and give
    it back, so nothing bills unseen. -> True when one was found."""
    for _ in range(4):
        try:
            hits = [i for i in list_instances() if i.get("name") == name]
        except AutoDLError:
            time.sleep(10)
            continue
        for item in hits:
            with locked():
                save({"uuid": item["uuid"], "app": "", "gpu": item.get("gpu_spec_uuid", ""), "price": 0.0, "cap": 0.0,
                      "created": time.time(), "last_used": time.time(), "comfy": "", "pid": os.getpid()})
            log("the create call failed but made %s anyway; giving it back" % item["uuid"])
            down(log=log, why="created without an answer")
        return bool(hits)
    log("WARNING: could not check whether a GPU was created; run: python3 autodl.py list")
    return False


def up(app_uuid, gpu_spec, price, cap, name="film", version="latest", log=print):
    """Create an instance and wait until it runs. -> state, with "comfy" as the address of port 6006."""
    if not price or not cap or price <= 0 or cap <= 0:
        raise AutoDLError("refusing to rent a GPU without an hourly price and a cap in yuan")
    with locked():
        held = load()
        if held:
            owner = held.get("pid")
            if owner and owner != os.getpid() and alive(owner):
                raise AutoDLError("instance %s is in use by another program on this machine (process %s); wait for it to finish"
                                  % (held.get("uuid"), owner))
            if held.get("uuid") and held.get("app") == app_uuid and held.get("gpu") == gpu_spec and status(held["uuid"]) == "running":
                held["pid"], held["last_used"] = os.getpid(), time.time()     # a GPU kept by an earlier run (--keep)
                save(held)
                watchdog_start()
                return held
            raise AutoDLError("this machine already holds instance %s; give it back first (autodl.py down)" % held.get("uuid"))
        tag = "%s-%s" % (name, os.urandom(3).hex())       # a one-off name, to find the instance if the answer to create is lost
        save({"uuid": None, "creating": tag, "pid": os.getpid(), "created": time.time(), "last_used": time.time()})
    tried, uuid = [], None
    try:
        for spec, list_price in [(gpu_spec, price)] + [g for g in FALLBACK_GPUS if g[0] != gpu_spec]:
            try:
                uuid = create(app_uuid, spec, tag, version)
                gpu_spec, price = spec, list_price
                break
            except AutoDLError as err:
                if "库存" not in str(err):
                    raise
                tried.append(spec)
                log("no %s in stock; trying the next GPU type" % spec)
        else:
            raise AutoDLError("no stock of any suitable GPU right now (tried %s); try again later" % ", ".join(tried))
    except AutoDLError as err:
        with locked():
            if (load() or {}).get("creating") == tag:
                os.remove(STATE)
        if "no stock of any" not in str(err):             # the call may have made one before its answer was lost
            adopt_orphan(tag, log=log)
        raise
    state = {"uuid": uuid, "app": app_uuid, "gpu": gpu_spec, "price": float(price), "cap": float(cap),
             "created": time.time(), "last_used": time.time(), "comfy": "", "pid": os.getpid(), "name": tag}
    with locked():
        save(state)                              # written before anything else, so it can always be given back
    LAST.clear()
    LAST.update(state)
    watchdog_start()
    log("created %s (%s at %.2f yuan an hour, cap %.2f); waiting for it to start" % (uuid, gpu_spec, price, cap))
    try:
        deadline, errors = time.time() + BOOT_TIMEOUT, 0
        while True:
            try:
                if status(uuid) == "running":
                    break
                errors = 0
            except AutoDLError:
                errors += 1                      # one dropped status call is not a failed boot
                if errors >= 6:
                    raise
            if time.time() > deadline:
                raise AutoDLError("instance %s did not start within %d minutes" % (uuid, BOOT_TIMEOUT // 60))
            time.sleep(8)
        snap = snapshot(uuid)
        host = snap.get("service_6006_domain")
        if not host:
            raise AutoDLError("instance %s runs but reports no address for port 6006" % uuid)
        state["comfy"] = "%s://%s" % ("https" if host.endswith(":8443") else snap.get("service_6006_port_protocol", "https"), host)
        if snap.get("payg_price"):
            state["price"] = snap["payg_price"] / 1000.0      # the price actually charged, in yuan an hour
        with locked():
            state["last_used"] = time.time()
            save(state)
        return state
    except Exception:
        down(log=log)
        raise


def down(log=print, why=""):
    """Power off, wait, release. Safe to call when nothing is held."""
    state = load()
    if not state:
        return 0.0
    uuid = state.get("uuid")
    if not uuid:                                         # a create still in flight, or one that never answered
        if not alive(state.get("pid")):
            with locked():
                os.remove(STATE)
            adopt_orphan(state.get("creating", ""), log=log)
        return 0.0
    problems = []
    try:
        if status(uuid) not in ("shutdown", "stopped"):
            power_off(uuid)
    except AutoDLError as err:
        problems.append(str(err))
    for _ in range(40):
        try:
            if status(uuid) in ("shutdown", "stopped"):
                break
        except AutoDLError:
            break
        time.sleep(5)
    released = False
    for _ in range(6):
        try:
            release(uuid)
            released = True
            break
        except AutoDLError as err:
            problems.append(str(err))
            time.sleep(10)
    if not released and not any(i.get("uuid") == uuid for i in safe_list()):
        released = True                                    # already gone
    spent = cost(state)                                  # billing runs until the power-off and release are done
    with locked():
        now = load()
        if now and now.get("uuid") == uuid and (released or not now.get("unreleased_logged")):
            with open(LEDGER, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({"uuid": uuid, "gpu": state["gpu"], "price": state["price"], "created": state["created"],
                                         "ended": time.time(), "yuan": spent, "released": released, "why": why}, ensure_ascii=False) + "\n")
            if released:
                os.remove(STATE)
            else:
                now["unreleased_logged"] = True
                save(now)
    if released:
        log("gave back %s after %.1f minutes, about %.2f yuan%s" % (uuid, (time.time() - state["created"]) / 60.0, spent, " (%s)" % why if why else ""))
    else:
        log("COULD NOT RELEASE %s: %s. It may still be billing; release it at https://www.autodl.art (我的 > 应用实例)."
            % (uuid, "; ".join(problems[-2:])))
    return spent


def safe_list():
    try:
        return list_instances()
    except AutoDLError:
        return [{"uuid": (load() or {}).get("uuid")}]


def sweep(log=print):
    state = load()
    if not state:
        return False
    if not state.get("uuid"):                           # a create in flight: only act if the program that made it has died
        if not alive(state.get("pid")):
            down(log=log, why="its program died while creating it")
            return True
        return False
    if time.time() - state["last_used"] > IDLE_LIMIT:
        down(log=log, why="idle more than 15 minutes")
        return True
    if cost(state) >= state["cap"]:
        down(log=log, why="reached the cap of %.2f yuan" % state["cap"])
        return True
    return False


def watchdog_start():
    """A detached process that keeps sweeping until the instance is gone. Only one runs at a time."""
    try:
        if alive(open(WATCHDOG_PID).read().strip()):
            return
    except OSError:
        pass
    subprocess.Popen([sys.executable, os.path.abspath(__file__), "watchdog"], stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


def watchdog():
    with open(WATCHDOG_PID, "w") as handle:
        handle.write(str(os.getpid()))
    while True:
        try:
            if not load():
                break
            sweep(log=lambda *_: None)
        except Exception:                                   # keep trying: this process is the last line of defence
            pass
        time.sleep(30)


def main():
    argv = sys.argv[1:]
    cmd = argv[0] if argv else ""

    def opt(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    try:
        if cmd == "list":
            items = list_instances()
            print("%d instance(s) on the account" % len(items))
            for i in items:
                print("  %s  %s  %s  %s  %s" % (i.get("uuid"), i.get("status"), i.get("gpu_spec_uuid"), i.get("region_name"),
                                                (i.get("cg_application_info") or {}).get("application_name")))
        elif cmd == "status":
            state = load()
            if not state:
                print("no instance held by this machine")
            else:
                print("%s  %s  %s  %.2f yuan/h  about %.2f yuan so far (cap %.2f)  idle %.1f min  %s"
                      % (state["uuid"], status(state["uuid"]), state["gpu"], state["price"], cost(state), state["cap"],
                         (time.time() - state["last_used"]) / 60.0, state.get("comfy", "")))
        elif cmd == "up":
            state = up(opt("--app"), opt("--gpu"), float(opt("--price", 0)), float(opt("--cap", 0)), opt("--name", "film"))
            print(state["comfy"])
        elif cmd == "down":
            down(why="asked")
        elif cmd == "sweep":
            if not sweep():
                print("nothing to give back")
        elif cmd == "watchdog":
            watchdog()
        else:
            sys.exit(__doc__)
    except AutoDLError as err:
        sys.exit("autodl: %s" % err)


if __name__ == "__main__":
    main()
