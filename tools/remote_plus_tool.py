#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from remote_plus_proto.parsers import (
    parse_computers_response,
    parse_configuration_read_response,
    parse_mediate_response,
)
from remote_plus_proto.protocol import AddressId, CommandId, build_frame, pack_auth_data
from remote_plus_proto.profiles import get_profile, load_profiles
from remote_plus_proto.runtime import RemotePlusRuntimeClient
from remote_plus_proto.screen_decode import decode_cygnus, decode_orion, decode_sirius, write_pgm


def cmd_build_auth(args: argparse.Namespace) -> None:
    print(pack_auth_data(args.username, args.hashed_password, args.address))


def cmd_build_frame(args: argparse.Namespace) -> None:
    frame = build_frame(
        dest=int(args.dest),
        src=int(args.src),
        cmd=int(args.cmd),
        payload_hex=args.payload_hex,
        sub=int(args.sub),
        block=int(args.block),
    )
    print(frame)


def cmd_parse(args: argparse.Namespace) -> None:
    if args.kind == "computers":
        out = parse_computers_response(args.data_hex)
    elif args.kind == "mediate":
        out = parse_mediate_response(args.data_hex)
    else:
        cfg = parse_configuration_read_response(args.data_hex)
        out = {
            "password": cfg["password"],
            "device_configs": [c.__dict__ for c in cfg["device_configs"]],
        }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def cmd_decode_screen(args: argparse.Namespace) -> None:
    fam = args.family.lower()
    if fam == "orion":
        w, h, px = decode_orion(args.screen_hex, fast=args.fast)
    elif fam == "cygnus":
        w, h, px = decode_cygnus(args.screen_hex, fast=args.fast)
    elif fam == "sirius":
        w, h, px = decode_sirius(args.screen_hex)
    else:
        raise SystemExit("family must be one of: orion, cygnus, sirius")
    write_pgm(args.out, w, h, px)
    print(f"written {args.out} ({w}x{h})")


def cmd_runtime_once(args: argparse.Namespace) -> None:
    client = RemotePlusRuntimeClient(host=args.host, port=args.port, timeout_sec=args.timeout)
    client.connect()
    try:
        if args.action == "config":
            msg = client.configuration_read(dest=args.dest)
        elif args.action == "screen":
            msg = client.capture_screen_fast(dest=args.dest, mode=args.mode)
        elif args.action == "key":
            if args.key is None:
                raise SystemExit("--key is required for action=key")
            msg = client.send_key(dest=args.dest, key_code=args.key)
        else:
            msg = client.main_group_read(dest=args.dest)
        print(
            json.dumps(
                {
                    "cmd": msg.cmd,
                    "src": msg.src,
                    "dest": msg.dest,
                    "blocks": msg.blocks,
                    "payload_hex_len": len(msg.payload_hex),
                    "payload_hex": msg.payload_hex,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        if args.close:
            client.close_remote(dest=args.dest)
        client.close_socket()


def cmd_profile(args: argparse.Namespace) -> None:
    if args.list:
        out = [{"family": p.family, "brandings": list(p.brandings)} for p in load_profiles()]
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return
    if not args.family:
        raise SystemExit("--family is required unless --list is used")
    p = get_profile(args.family, args.branding)
    out = {
        "family": p.family,
        "brandings": list(p.brandings),
        "screen": {
            "width": p.screen.width,
            "height": p.screen.height,
            "decoder": p.screen.decoder,
        },
        "capture": {
            "default_command": p.capture.default_command,
            "supports_fast": p.capture.supports_fast,
        },
        "keys": p.keys,
    }
    if args.key:
        if args.key not in p.keys:
            raise SystemExit(f"unknown key '{args.key}' for family={p.family}")
        out = {"family": p.family, "key": args.key, "code": p.keys[args.key]}
    print(json.dumps(out, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Remote+ protocol utility")
    sub = p.add_subparsers(required=True)

    p_auth = sub.add_parser("build-auth")
    p_auth.add_argument("--username", required=True)
    p_auth.add_argument("--hashed-password", required=True)
    p_auth.add_argument("--address", default="")
    p_auth.set_defaults(func=cmd_build_auth)

    p_frame = sub.add_parser("build-frame")
    p_frame.add_argument("--dest", default=str(AddressId.SMARTLINK_SERVER))
    p_frame.add_argument("--src", default=str(AddressId.PC))
    p_frame.add_argument("--cmd", default=str(CommandId.COMPUTERS_REQUEST))
    p_frame.add_argument("--payload-hex", default="")
    p_frame.add_argument("--sub", default="0")
    p_frame.add_argument("--block", default="0")
    p_frame.set_defaults(func=cmd_build_frame)

    p_parse = sub.add_parser("parse-response")
    p_parse.add_argument("--kind", choices=["computers", "mediate", "config"], required=True)
    p_parse.add_argument("--data-hex", required=True)
    p_parse.set_defaults(func=cmd_parse)

    p_scr = sub.add_parser("decode-screen")
    p_scr.add_argument("--family", required=True)
    p_scr.add_argument("--screen-hex", required=True)
    p_scr.add_argument("--fast", action="store_true")
    p_scr.add_argument("--out", required=True)
    p_scr.set_defaults(func=cmd_decode_screen)

    p_run = sub.add_parser("runtime-once")
    p_run.add_argument("--host", required=True)
    p_run.add_argument("--port", type=int, default=5843)
    p_run.add_argument("--dest", type=int, required=True, help="device destination address")
    p_run.add_argument("--timeout", type=float, default=20.0)
    p_run.add_argument("--action", choices=["config", "screen", "key", "main-group"], default="screen")
    p_run.add_argument("--mode", type=int, default=0, help="screen mode for action=screen")
    p_run.add_argument("--key", type=int, help="key code for action=key")
    p_run.add_argument("--close", action="store_true", help="send CLOSE command before socket close")
    p_run.set_defaults(func=cmd_runtime_once)

    p_prof = sub.add_parser("profile")
    p_prof.add_argument("--list", action="store_true", help="list known families")
    p_prof.add_argument("--family", help="family name: orion/cygnus/sirius")
    p_prof.add_argument("--branding", help="optional branding selector")
    p_prof.add_argument("--key", help="print only one key code")
    p_prof.set_defaults(func=cmd_profile)
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
