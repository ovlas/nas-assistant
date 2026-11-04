"""Pairing the phone app: the QR code on the page."""

import re


def test_the_qr_code_scales_to_its_box(client, alice):
    svg = client.post("/api/devices/pairing", headers=alice).json()["qr_svg"]
    # The page sizes the SVG with CSS: a fixed width/height without a viewBox crops the code.
    assert re.search(r'viewBox="0 0 \d+ \d+"', svg)
    assert not re.search(r'<svg[^>]* width=', svg)
