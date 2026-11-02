"""Build and verify explicit static web projections. Python 3.10+, standard library only."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import runpy
from urllib.parse import urlparse
import zipfile

SCHEMA = 'static-web-bake.release.v1'
RESERVED = {'release.json', 'resources.json', '.nojekyll'}
PRIVATE = {'.git', '.env', 'auth.json', 'config.toml', 'credentials.json', 'id_rsa'}
DEVICES = {'con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)), *(f'lpt{i}' for i in range(1, 10))}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def encode(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def clean_path(value):
    if not isinstance(value, str) or not value or any(ord(c) < 32 for c in value) or any(c in value for c in '\\:#?%*<>|"'):
        raise ValueError('Use a plain relative POSIX file path: ' + repr(value))
    p = PurePosixPath(value)
    if p.is_absolute() or value != p.as_posix() or any(x in ('.', '..') for x in value.split('/')):
        raise ValueError('Path must stay within its owner: ' + value)
    for part in p.parts:
        lower = part.casefold()
        if lower in PRIVATE or lower.startswith('.env.') or part.endswith((' ', '.')) or lower.split('.')[0] in DEVICES:
            raise ValueError('Private or nonportable path is not publishable: ' + value)
    return value


def no_links(path):
    path = Path(path).absolute()
    for p in (path, *path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.stat(follow_symlinks=False), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Preserve linked paths: ' + str(p))
    return path


def source_bytes(root, relative):
    path = no_links(root / clean_path(relative))
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing source file or escaped owner: ' + relative)
    return path.read_bytes()


def disjoint(a, b):
    a, b = Path(a).resolve(), Path(b).resolve()
    if a.is_relative_to(b) or b.is_relative_to(a):
        raise ValueError('Source and destination directories must be separate')


def fresh(path):
    path = no_links(path)
    if path.exists():
        raise ValueError('Preserve existing output; choose a new destination: ' + str(path))
    return path


def public_url(value):
    if not isinstance(value, str):
        raise ValueError('URL must be a string')
    u = urlparse(value)
    if u.scheme != 'https' or not u.netloc or u.username or u.password:
        raise ValueError('External originals require a public HTTPS URL without credentials')
    return value


def descriptor(data, path):
    return {'path': path, 'sha256': sha(data), 'bytes': len(data)}


def build(config_path, destination):
    config_path = no_links(config_path)
    cfg, root = read(config_path), config_path.parent
    if cfg.get('schema') != 'static-web-bake.config.v1':
        raise ValueError('Unsupported build configuration')
    out = fresh(destination)
    disjoint(root, out)
    entry = clean_path(cfg.get('entry', 'index.html'))
    if not entry.endswith('.html') or not isinstance(cfg.get('title'), str):
        raise ValueError('Set a title and an HTML entry')
    blobs, names, records = {}, {}, []

    def add(name, data, role):
        name = clean_path(name)
        key = name.casefold()
        if any(part.casefold() in RESERVED for part in PurePosixPath(name).parts) or key in names:
            raise ValueError('Duplicate, reserved or case-colliding output: ' + name)
        names[key] = name
        blobs[name] = data
        records.append({**descriptor(data, name), 'role': role})

    def asset(relative, role):
        data = source_bytes(root, relative)
        suffix = Path(relative).suffix.lower()
        if not re.fullmatch(r'\.[a-z0-9]{1,12}', suffix):
            raise ValueError('Asset needs a simple extension')
        name = 'assets/' + sha(data) + suffix
        if name not in blobs:
            add(name, data, role)
        return descriptor(data, name)

    for item in cfg.get('files', []):
        add(item['path'], source_bytes(root, item['source']), 'shell')
    if entry not in blobs:
        raise ValueError('Entry must be explicitly listed in files')
    resources, ids = [], set()
    image_info = runpy.run_path(str(Path(__file__).with_name('image_metadata.py')))['dimensions']
    image_sizes = {}
    for item in cfg.get('resources', []):
        ident = item.get('id')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', ident) or ident in ids:
            raise ValueError('Resource ID is missing or duplicated')
        ids.add(ident)
        row = {'id': ident, 'name': item['name'], 'category': item.get('category', '未分类'), 'tags': item.get('tags', [])}
        if not isinstance(row['name'], str) or not isinstance(row['category'], str) or not isinstance(row['tags'], list) or any(not isinstance(x, str) for x in row['tags']):
            raise ValueError('Resource metadata types are invalid')
        if 'groupPath' in item:
            row['groupPath'] = item['groupPath']
        if 'credit' in item:
            if not isinstance(item['credit'], str):
                raise ValueError('Credit must be text')
            row['credit'] = item['credit']
        if 'preview' in item:
            preview = item['preview']
            if preview['kind'] not in ('image', 'audio', 'video', 'text'):
                raise ValueError('Use a dedicated renderer for this preview type')
            row['preview'] = {**asset(preview['source'], 'preview'), 'kind': preview['kind']}
            if preview['kind'] == 'image':
                key = (row['preview']['path'], preview.get('width'), preview.get('height'))
                if key not in image_sizes:
                    image_sizes[key] = image_info(blobs[row['preview']['path']], Path(preview['source']).suffix.lower(), preview)
                row['preview'].update(image_sizes[key])
        if 'original' in item:
            original = item['original']
            public = {'path': clean_path(original['path'])}
            if 'source' in original:
                data = source_bytes(root, original['source'])
                public.update(sha256=sha(data), bytes=len(data))
                if original.get('include') is True:
                    public['url'] = asset(original['source'], 'original')['path']
            elif 'sha256' in original and 'bytes' in original:
                if not re.fullmatch(r'[a-f0-9]{64}', original['sha256']) or type(original['bytes']) is not int or original['bytes'] < 0:
                    raise ValueError('External original identity is invalid')
                public.update(sha256=original['sha256'], bytes=original['bytes'])
            if 'url' in original:
                if original.get('include') is True or 'sha256' not in public:
                    raise ValueError('Specify one original location with its content identity')
                public['url'] = public_url(original['url'])
            row['original'] = public
        resources.append(row)
    if 'resources' in cfg:
        library_id = cfg.get('libraryId', 'gallery-' + sha(cfg['title'].encode('utf-8'))[:16])
        if not isinstance(library_id, str) or not library_id.strip():
            raise ValueError('libraryId must be nonempty text')
        project = runpy.run_path(str(Path(__file__).with_name('resource_groups.py')))['project_resources']
        catalog = encode(project(cfg['title'], resources, library_id))
        blobs['resources.json'] = catalog
        records.append({**descriptor(catalog, 'resources.json'), 'role': 'catalog'})
    blobs['.nojekyll'] = b''
    records.append({**descriptor(b'', '.nojekyll'), 'role': 'host'})
    spellings = {}
    for name in [*blobs, 'RELEASE.json']:
        path = PurePosixPath(name)
        for prefix in (path, *path.parents):
            spelling = prefix.as_posix()
            if spelling == '.':
                continue
            key = spelling.casefold()
            if key in spellings and spellings[key] != spelling:
                raise ValueError('Output directory/file spelling differs only by case: ' + spelling)
            spellings[key] = spelling
    # File-vs-directory conflicts must fail before the first output byte is written.
    for name in blobs:
        if any(parent.as_posix().casefold() in names for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
            raise ValueError('Output contains a file/directory collision: ' + name)
    manifest = {'schema': SCHEMA, 'title': cfg['title'], 'entry': entry, 'files': sorted(records, key=lambda x: x['path'])}
    out.mkdir(parents=True)
    for name, data in blobs.items():
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (out / 'RELEASE.json').write_bytes(encode(manifest))
    return verify(out)


def verify(site):
    site = no_links(site)
    manifest_path = no_links(site / 'RELEASE.json')
    manifest = read(manifest_path)
    if manifest.get('schema') != SCHEMA:
        raise ValueError('Unknown release owner/schema')
    expected, folded = {}, set()
    for item in manifest['files']:
        name = clean_path(item['path'])
        if name.casefold() in folded or name.casefold() == 'release.json':
            raise ValueError('Duplicate/reserved release path')
        folded.add(name.casefold())
        if not re.fullmatch(r'[a-f0-9]{64}', item['sha256']) or type(item['bytes']) is not int or item['bytes'] < 0:
            raise ValueError('Invalid release content identity')
        expected[name] = item
    if clean_path(manifest['entry']) not in expected:
        raise ValueError('Release has no declared entry')
    actual = set()
    for path in site.rglob('*'):
        no_links(path)
        if path.is_file():
            actual.add(path.relative_to(site).as_posix())
    if actual != set(expected) | {'RELEASE.json'}:
        raise ValueError('Unknown or missing release files; preserve this directory')
    for name, item in expected.items():
        data = (site / name).read_bytes()
        if len(data) != item['bytes'] or sha(data) != item['sha256']:
            raise ValueError('Release identity drift: ' + name)
    return {'site': str(site), 'entry': manifest['entry'], 'files': len(expected), 'bytes': sum(x['bytes'] for x in expected.values()), 'releaseSha256': sha(manifest_path.read_bytes())}


RUNNER = '''"""Local offline site server. No subprocesses or external network dependency."""
import argparse,functools,http.server,json,sys,urllib.parse,webbrowser
from pathlib import Path
root=Path(__file__).resolve().parent/'site'
manifest=json.loads((root/'RELEASE.json').read_text(encoding='utf-8'))
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8000);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
if not 1<=args.port<=65535:parser.error('port must be between 1 and 65535')
handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root))
try:server=http.server.ThreadingHTTPServer(('127.0.0.1',args.port),handler)
except OSError as e:raise SystemExit('Local port unavailable; use --port with another port: '+str(e))
url='http://127.0.0.1:'+str(args.port)+'/'+urllib.parse.quote(manifest['entry'])
print(url,flush=True)
try:
 if not args.no_browser:webbrowser.open(url)
 server.serve_forever()
except KeyboardInterrupt:pass
finally:server.server_close()
'''


def pack(site, destination):
    site = no_links(site)
    out = fresh(destination)
    if out.suffix.lower() != '.zip' or out.resolve().is_relative_to(site.resolve()):
        raise ValueError('Choose a new ZIP outside the site')
    result = verify(site)
    manifest_bytes = (site / 'RELEASE.json').read_bytes()
    if sha(manifest_bytes) != result['releaseSha256']:
        raise ValueError('Release changed during packaging')
    manifest = json.loads(manifest_bytes)
    out.parent.mkdir(parents=True, exist_ok=True)
    archive = zipfile.ZipFile(out, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6)
    try:
        with archive:
            for item in sorted(manifest['files'], key=lambda x: x['path']):
                digest, count = hashlib.sha256(), 0
                with no_links(site / item['path']).open('rb') as source, archive.open('site/' + item['path'], 'w', force_zip64=True) as target:
                    while chunk := source.read(1024 * 1024):
                        count += len(chunk)
                        digest.update(chunk)
                        target.write(chunk)
                if count != item['bytes'] or digest.hexdigest() != item['sha256']:
                    raise ValueError('Release changed during packaging: ' + item['path'])
            archive.writestr('site/RELEASE.json', manifest_bytes)
            archive.writestr('run.py', RUNNER.encode('utf-8'))
            if verify(site)['releaseSha256'] != result['releaseSha256']:
                raise ValueError('Release changed during packaging')
    except BaseException:
        out.unlink(missing_ok=True)
        raise
    return {'archive': str(out), 'bytes': out.stat().st_size, 'sha256': sha(out.read_bytes()), 'siteReleaseSha256': result['releaseSha256']}


def diff(before, after):
    verify(before)
    verify(after)
    old_manifest = read(Path(before) / 'RELEASE.json')
    new_manifest = read(Path(after) / 'RELEASE.json')
    a = {x['path']: x for x in old_manifest['files']}
    b = {x['path']: x for x in new_manifest['files']}
    added, removed = sorted(b.keys() - a.keys()), sorted(a.keys() - b.keys())
    changed = sorted(name for name in a.keys() & b.keys() if a[name]['sha256'] != b[name]['sha256'])
    metadata_changed = sorted(key for key in ('title', 'entry') if old_manifest.get(key) != new_manifest.get(key))
    return {'added': added, 'removed': removed, 'changed': changed, 'releaseFieldsChanged': metadata_changed, 'changedBytes': sum(b[x]['bytes'] for x in added + changed), 'mutatesExistingReleases': False, 'automaticUpdateProduced': False}



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('build'); p.add_argument('--config', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = commands.add_parser('verify'); p.add_argument('--site', type=Path, required=True)
    p = commands.add_parser('pack'); p.add_argument('--site', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = commands.add_parser('diff'); p.add_argument('--before', type=Path, required=True); p.add_argument('--after', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build': result = build(args.config, args.out)
    elif args.command == 'verify': result = verify(args.site)
    elif args.command == 'pack': result = pack(args.site, args.out)
    else: result = diff(args.before, args.after)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(str(error))
