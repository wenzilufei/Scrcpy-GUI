def parse_device_name(name_data: bytes) -> str:
    return name_data.split(b"\x00", 1)[0].decode("utf-8", errors="replace")


def parse_codec_meta(codec_meta: bytes):
    codec_id = int.from_bytes(codec_meta[0:4], byteorder="big")
    video_width = int.from_bytes(codec_meta[4:8], byteorder="big")
    video_height = int.from_bytes(codec_meta[8:12], byteorder="big")
    return codec_id, video_width, video_height

