#!/usr/bin/env python3

import argparse
import csv
import json
import socket

HOST = "0.cloud.chals.io"

PRNS = [1, 2, 7, 14, 15, 17, 19, 20, 22, 30]


def main():

    ap = argparse.ArgumentParser()
    ap.add_argument("port", type=int)
    ap.add_argument(
        "-o",
        "--output",
        default="truth_log.csv"
    )

    args = ap.parse_args()

    s = socket.create_connection((HOST, args.port), timeout=10)
    print(f"[+] Connected to {HOST}:{args.port}")

    s.settimeout(1.0)

    fp = open(args.output, "w", newline="")

    writer = csv.writer(fp)

    header = [
        "gps_time",
        "scenario_seconds",
        "lat",
        "lon",
        "alt",
    ]

    for prn in PRNS:
        header += [
            f"prn{prn}_doppler",
            f"prn{prn}_cn0",
            f"prn{prn}_state",
        ]

    writer.writerow(header)

    buf = b""

    print("[*] Logging... Ctrl+C to stop")

    try:

        while True:

            try:

                d = s.recv(4096)

                if not d:
                    print("[*] Server closed.")
                    break

                buf += d

                while b"\n" in buf:

                    line, buf = buf.split(b"\n", 1)

                    if not line:
                        continue

                    obj = json.loads(line)

                    row = [
                        obj["gps_time"],
                        obj["scenario_seconds"],
                        obj["location"]["lat"],
                        obj["location"]["lon"],
                        obj["location"]["alt"],
                    ]

                    obs = {
                        x["prn"]: x
                        for x in obj["observables"]
                    }

                    for prn in PRNS:

                        if prn in obs:

                            row += [
                                obs[prn]["doppler_hz"],
                                obs[prn]["cn0_dbhz"],
                                obs[prn]["tracking_state"],
                            ]

                        else:

                            row += ["", "", ""]

                    writer.writerow(row)
                    fp.flush()

                    print(
                        f'{obj["gps_time"]}  '
                        f'Lat={obj["location"]["lat"]:.6f}  '
                        f'Lon={obj["location"]["lon"]:.6f}'
                    )

            except socket.timeout:
                try:
                    s.sendall(b"\n")
                except OSError:
                    break

    except KeyboardInterrupt:
        print("\n[*] Interrupted.")

    finally:

        fp.close()

        try:
            s.close()
        except:
            pass

        print(f"[+] Saved -> {args.output}")


if __name__ == "__main__":
    main()
