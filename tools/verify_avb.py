#!/usr/bin/env python3
"""Verify embedded vbmeta signature, hash descriptors and all six Merkle trees.
Does not establish an independent Google trust anchor or validate FEC parity.
"""
import argparse, hashlib, json, pathlib
import avbtool as avb
ROOT = pathlib.Path(__file__).resolve().parents[1]
directory = ROOT/'extracted/ruby'
parser = argparse.ArgumentParser()
parser.add_argument('--slot', choices=['a', 'b'], default='a')
slot = parser.parse_args().slot
blob = (directory/f'vbmeta_{slot}.img').read_bytes()
image = avb.ImageHandler(str(directory/f'vbmeta_{slot}.img'), read_only=True)
_, header, descriptors, _ = avb.Avb()._parse_image(image)
result = {'embedded_key_signature_valid': avb.verify_vbmeta_signature(header, blob),
          'flags': header.flags, 'rollback_index': header.rollback_index,
          'trust_anchor': 'embedded key only; official HTTPS/catalog provenance separately',
          'fec_checked': False, 'partitions': []}
gpt = {p['name']: p for p in json.loads((directory/'gpt.json').read_text())}
lp = {p['name']: p for p in json.loads((directory/'super.json').read_text())['slots'][0]['partitions']}
class Window:
    def __init__(self, file, offset): self.file, self.offset = file, offset
    def seek(self, pos): return self.file.seek(self.offset+pos)
    def read(self, size): return self.file.read(size)
with (ROOT/'downloads/ruby-recovery.raw').open('rb') as raw:
    for d in descriptors:
        if not isinstance(d, (avb.AvbHashDescriptor, avb.AvbHashtreeDescriptor)): continue
        name = d.partition_name+'_'+slot
        p = gpt.get(name) or lp[name]
        offset = p.get('offset') if 'offset' in p else p['extents'][0]['absolute_offset']
        w = Window(raw, offset)
        if isinstance(d, avb.AvbHashDescriptor):
            w.seek(0); h = hashlib.new(d.hash_algorithm); h.update(d.salt)
            left = d.image_size
            while left:
                data = w.read(min(left, 4*1024*1024)); assert data
                h.update(data); left -= len(data)
            valid = h.digest() == d.digest
            row = {'name': name, 'type': 'hash', 'bytes': d.image_size, 'valid': valid}
        else:
            digest_size = d._hashtree_digest_size()
            padding = avb.round_to_pow2(digest_size)-digest_size
            offsets, size = avb.calc_hash_level_offsets(d.image_size, d.data_block_size, digest_size+padding)
            root, tree = avb.generate_hash_tree(w, d.image_size, d.data_block_size,
                d.hash_algorithm, d.salt, padding, offsets, size)
            w.seek(d.tree_offset)
            row = {'name': name, 'type': 'hashtree', 'bytes': d.image_size,
                   'root_valid': root == d.root_digest,
                   'tree_valid': tree == w.read(d.tree_size), 'root_digest': root.hex()}
        result['partitions'].append(row)
        print(row, flush=True)
(ROOT/'evidence'/('avb-verification.json' if slot == 'a' else 'avb-verification-b.json')).write_text(json.dumps(result, indent=2)+'\n')
assert result['embedded_key_signature_valid']
assert all(p.get('valid', p.get('root_valid') and p.get('tree_valid')) for p in result['partitions'])
