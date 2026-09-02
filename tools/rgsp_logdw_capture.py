#!/usr/bin/env python3
import argparse
import os
import select
import socket
import time


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--seconds", type=float, default=10.0)
    args = parser.parse_args()

    try:
        os.unlink(args.path)
    except FileNotFoundError:
        pass

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(args.path)
    os.chmod(args.path, 0o666)
    deadline = time.monotonic() + args.seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        readable, _, _ = select.select([sock], [], [], remaining)
        if not readable:
            break
        data = sock.recv(65535)
        print(data.decode("utf-8", errors="backslashreplace"), flush=True)


if __name__ == "__main__":
    main()
