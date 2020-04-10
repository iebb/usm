import struct
import sys
from io import BytesIO

BLOCK_TYPES = {
    b'CRID': ('b', 4),
    b'@ALP': ('b', 4),
    b'@SFV': ('b', 4),
    b'@SFA': ('b', 4),
    b'@SBT': ('b', 4),
    b'@CUE': ('b', 4),
}

BLOCK_ID_LENGTH = 4
MPEG_START_BYTES = b'CRID'

HEADER_END_BYTES = b'\x23\x48\x45\x41\x44\x45\x52\x20' \
                   b'\x45\x4E\x44\x20\x20\x20\x20\x20' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x3D' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x00'

METADATA_END_BYTES = b'\x23\x4D\x45\x54\x41\x44\x41\x54' \
                   b'\x41\x20\x45\x4E\x44\x20\x20\x20' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x3D' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x00'
CONTENTS_END_BYTES = b'\x23\x43\x4F\x4E\x54\x45\x4E\x54' \
                   b'\x53\x20\x45\x4E\x44\x20\x20\x20' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x3D' \
                   b'\x3D\x3D\x3D\x3D\x3D\x3D\x3D\x00'


def demultiplex(filename):
    file = open(filename, "rb").read()
    size = len(file)
    offset = file.find(MPEG_START_BYTES)
    writers = {}

    videos = {}
    audios = {}
    alphas = {}

    if offset == -1:
        print("not found")
        return
    while offset < size:
        block_id = file[offset:offset+BLOCK_ID_LENGTH]
        if block_id in BLOCK_TYPES:
            typ, val = BLOCK_TYPES[block_id]
            if typ == 'b':  # usm are 4-byte
                bs_size = val
                offset2 = offset+BLOCK_ID_LENGTH
                bs_array = file[offset2 : offset2+bs_size]
                block_size = struct.unpack('>I', bs_array)[0]

                block_val = struct.unpack('<I', block_id)[0]
                # print(block_id, block_val)
                is_audio = (block_id == b'@SFA')
                is_video = (block_id == b'@SFV')
                is_alpha = (block_id == b'@ALP')

                base_pos = offset + BLOCK_ID_LENGTH + bs_size

                if is_audio or is_video or is_alpha:
                    stream_id = file[offset + 12] if is_audio else 0
                    stream_ik = stream_id | block_val
                    if is_audio:
                        audios[stream_ik] = 1
                        stream_key = ('a', stream_id | block_val)
                    elif is_video:
                        videos[stream_ik] = 1
                        stream_key = ('v', stream_id | block_val)
                    else:
                        alphas[stream_ik] = 1
                        stream_key = ('x', stream_id | block_val)

                    if stream_key not in writers:
                        writers[stream_key] = BytesIO()

                    header_size = struct.unpack('>H', file[offset+8:offset+10])[0]
                    footer_size = struct.unpack('>H', file[offset+10:offset+12])[0]
                    if header_size + footer_size < block_size:
                        start_pos = base_pos + header_size
                        end_pos = base_pos + block_size - footer_size
                        writers[stream_key].write(
                            file[start_pos:end_pos]
                        )

                offset += BLOCK_ID_LENGTH + bs_size + block_size

    for stream_key in writers:
        val = writers[stream_key].getvalue()
        header_pos = val.find(HEADER_END_BYTES)
        meta_pos = val.find(METADATA_END_BYTES)
        footer_pos = val.find(CONTENTS_END_BYTES)
        start_pos = max(header_pos, meta_pos) + 32
        typ, key = stream_key
        if typ == 'v':
            fn = filename + ".m2v"
            if len(videos) > 1:
                fn = filename + ".%08x.m2v" % key
            print("writing %s, %d bytes" % (fn, footer_pos - start_pos))
            open(fn, "wb+").write(val[start_pos: footer_pos])
        elif typ == 'x':
            fn = filename + ".alp"
            if len(videos) > 1:
                fn = filename + ".%08x.alp" % key
            print("writing %s, %d bytes" % (fn, footer_pos - start_pos))
            open(fn, "wb+").write(val[start_pos: footer_pos])
        elif typ == 'a':
            fn = filename + ".adx"
            if len(alphas) > 1:
                fn = filename + ".%08x.adx" % key
            print("writing %s, %d bytes" % (fn, footer_pos - start_pos))
            open(fn, "wb+").write(val[start_pos: footer_pos])


if __name__ == "__main__":
    demultiplex(sys.argv[1])

