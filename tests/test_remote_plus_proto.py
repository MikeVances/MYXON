from __future__ import annotations

import unittest

from tools.remote_plus_proto.parsers import (
    parse_computers_response,
    parse_configuration_read_response,
    parse_main_group_response,
    parse_mediate_response,
)
from tools.remote_plus_proto.profiles import get_profile, load_profiles
from tools.remote_plus_proto.protocol import (
    AddressId,
    CommandId,
    SubCommand,
    build_frame,
    parse_frame,
    pack_auth_data,
)
from tools.remote_plus_proto.reassembly import FrameStreamReassembler
from tools.remote_plus_proto.screen_decode import decode_cygnus, decode_orion, decode_sirius
from tools.remote_plus_proto.session_engine import SessionEngine


class TestProtocol(unittest.TestCase):
    def test_build_parse_frame_roundtrip(self) -> None:
        frame_text = build_frame(
            dest=int(AddressId.SMARTLINK_SERVER),
            src=int(AddressId.PC),
            cmd=int(CommandId.COMPUTERS_REQUEST),
            payload_hex="414243",
            sub=int(SubCommand.BEGIN),
            block=0,
        )
        frame = parse_frame(frame_text)
        self.assertEqual(frame.dest, int(AddressId.SMARTLINK_SERVER))
        self.assertEqual(frame.src, int(AddressId.PC))
        self.assertEqual(frame.cmd, int(CommandId.COMPUTERS_REQUEST))
        self.assertEqual(frame.sub, int(SubCommand.BEGIN))
        self.assertEqual(frame.block, 0)
        self.assertEqual(frame.payload_hex, "414243")

    def test_crc_mismatch_raises(self) -> None:
        frame_text = build_frame(
            dest=int(AddressId.SMARTLINK_SERVER),
            src=int(AddressId.PC),
            cmd=int(CommandId.CLOSE),
            payload_hex="",
        )
        tampered = frame_text[:-3] + "00*\r"
        with self.assertRaises(ValueError):
            parse_frame(tampered)

    def test_pack_auth_data_layout(self) -> None:
        auth = pack_auth_data("demo", "ABCD", "42")
        self.assertTrue(auth.startswith("64656D6F"))
        self.assertEqual(len(auth), 40 + 40 + 4)
        self.assertTrue(auth[40:80].endswith("ABCD"))
        self.assertTrue(auth.endswith("3432"))


class TestParsers(unittest.TestCase):
    def test_parse_mediate_response(self) -> None:
        out = parse_mediate_response("010001")
        self.assertEqual(out["username_status"], 1)
        self.assertEqual(out["password_status"], 0)
        self.assertEqual(out["mediation_status"], 1)

    def test_parse_configuration_read_response(self) -> None:
        # password + 1 full row
        data = "0001" + "0001000200030004000500060000000700080009"
        out = parse_configuration_read_response(data)
        self.assertEqual(out["password"], 1)
        self.assertEqual(len(out["device_configs"]), 1)
        cfg = out["device_configs"][0]
        self.assertEqual(cfg.computer, 1)
        self.assertEqual(cfg.sort, 2)
        self.assertEqual(cfg.type, 3)
        self.assertEqual(cfg.company, 4)
        self.assertEqual(cfg.computer_version, 5)
        self.assertEqual(cfg.pc_version, 6)
        self.assertEqual(cfg.serial, 7)
        self.assertEqual(cfg.number, 8)
        self.assertEqual(cfg.options_change_count, 9)

    def test_parse_computers_response(self) -> None:
        # statuses + one 60-hex row: address(10 bytes) + name(20 bytes)
        addr = "31323334350000000000"  # "12345"
        name = "44656D6F00000000000000000000000000000000"  # "Demo"
        out = parse_computers_response("0101" + addr + name)
        self.assertEqual(out["username_status"], 1)
        self.assertEqual(out["password_status"], 1)
        self.assertEqual(len(out["connections"]), 1)
        self.assertEqual(out["connections"][0]["address"], "12345\x00\x00\x00\x00\x00")
        self.assertEqual(out["connections"][0]["name"], "Demo")

    def test_parse_main_group_response(self) -> None:
        out = parse_main_group_response("00FF112233", alarm_offset=4, alarm_len=2)
        self.assertEqual(out["code"], 0x00FF)
        self.assertEqual(out["alarm_raw"], 0x11)


class TestReassemblyAndSession(unittest.TestCase):
    def test_reassembly_from_chunks(self) -> None:
        frame1 = build_frame(1184, 1023, int(CommandId.CLOSE), "")
        frame2 = build_frame(1184, 1023, int(CommandId.MAIN_GROUP_READ), "")
        stream = FrameStreamReassembler()
        out = []
        for chunk in (frame1[:5], frame1[5:] + frame2[:3], frame2[3:]):
            out.extend(stream.feed(chunk))
        self.assertEqual(out, [frame1, frame2])

    def test_session_engine_accumulates_begin_next_end(self) -> None:
        engine = SessionEngine()
        f1 = parse_frame(build_frame(1184, 1023, 6, "AA", sub=int(SubCommand.BEGIN), block=0))
        f2 = parse_frame(build_frame(1184, 1023, 6, "BB", sub=int(SubCommand.NEXT), block=1))
        f3 = parse_frame(build_frame(1184, 1023, 6, "CC", sub=int(SubCommand.END), block=2))
        self.assertEqual(engine.feed(f1), [])
        self.assertEqual(engine.feed(f2), [])
        done = engine.feed(f3)
        self.assertEqual(len(done), 1)
        self.assertEqual(done[0].payload_hex, "AABBCC")
        self.assertEqual(done[0].blocks, [0, 1, 2])


class TestScreenDecodeAndProfiles(unittest.TestCase):
    def test_decode_orion_small_pattern(self) -> None:
        w, h, px = decode_orion("AA", fast=False)
        self.assertEqual((w, h), (240, 128))
        self.assertEqual(len(px), w * h)
        self.assertGreater(sum(1 for v in px if v == 255), 0)

    def test_decode_cygnus_small_pattern(self) -> None:
        w, h, px = decode_cygnus("AA", fast=False)
        self.assertEqual((w, h), (128, 64))
        self.assertEqual(len(px), w * h)
        self.assertGreater(sum(1 for v in px if v == 255), 0)

    def test_decode_sirius_small_pattern(self) -> None:
        w, h, px = decode_sirius("01")
        self.assertEqual((w, h), (122, 32))
        self.assertEqual(len(px), w * h)
        self.assertEqual(px[0], 0)

    def test_profiles_resolve(self) -> None:
        profiles = load_profiles()
        self.assertGreaterEqual(len(profiles), 3)
        p = get_profile("orion")
        self.assertEqual(p.family, "orion")
        self.assertTrue(p.screen.decoder)


if __name__ == "__main__":
    unittest.main()
