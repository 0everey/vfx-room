"""Project explicit resource group paths into stable trees and original plans."""
import hashlib
import json
from pathlib import PurePosixPath


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def project_resources(title, resources, library_id):
    nodes, assets = {}, {}

    def node(view, path, label, parent=None):
        ident = view + ':' + hashlib.sha256(encoded(path)).hexdigest()[:24]
        if ident not in nodes:
            nodes[ident] = {'id': ident, 'parentId': parent, 'label': label, 'kind': view, 'children': [], 'directItems': [], 'count': 0}
            if parent is not None:
                nodes[parent]['children'].append(ident)
        elif nodes[ident]['label'] != label:
            raise ValueError('Same group key has conflicting display labels')
        return ident

    roots = {'semantic': node('semantic', [], '资源分组'), 'directory': node('directory', [], '原库目录')}
    for resource in resources:
        original = resource.get('original', {})
        file_ids = []
        if original.get('url'):
            ident = 'original-' + resource['id']
            assets[ident] = {'url': original['url'], 'sourceRelative': original['path'], 'name': PurePosixPath(original['path']).name, 'bytes': original['bytes'], 'sha256': original['sha256']}
            file_ids.append(ident)
        resource['files'] = file_ids
        resource['downloadFingerprint'] = hashlib.sha256(encoded([{'id': ident, **assets[ident]} for ident in file_ids] or {'id':resource['id'],'path':original.get('path')})).hexdigest()
        category = resource.get('category', '').strip() or '未分类'
        path = resource['groupPath'] if 'groupPath' in resource else [category]
        if not isinstance(path, list) or len(path) > 128:
            raise ValueError('groupPath must be an array with at most 128 levels')
        keys, current = [], roots['semantic']
        for part in path:
            if isinstance(part, str):
                key, label = part, part
            elif isinstance(part, dict):
                key, label = part.get('key'), part.get('label')
            else:
                raise ValueError('groupPath levels must be text or {key,label}')
            if not isinstance(key, str) or not key.strip() or not isinstance(label, str) or not label.strip():
                raise ValueError('Group keys and labels must be nonempty text')
            keys.append(key)
            current = node('semantic', keys, label, current)
        nodes[current]['directItems'].append(resource['id'])
        resource['semanticGroup'] = current
        current, keys = roots['directory'], []
        directory = list(PurePosixPath(original.get('path', 'preview-only/file')).parts[:-1])
        for part in directory:
            keys.append(part)
            current = node('directory', keys, part, current)
        nodes[current]['directItems'].append(resource['id'])
        resource['directoryGroup'] = current

    def count(ident):
        members = set(nodes[ident]['directItems'])
        nodes[ident]['children'].sort(key=lambda key: (nodes[key]['label'].casefold(), key))
        for child in nodes[ident]['children']:
            members.update(count(child))
        nodes[ident]['count'] = len(members)
        return members
    for root in roots.values():
        assert len(count(root)) == len(resources)
    hierarchy = {'roots': roots, 'nodes': nodes}
    revision = hashlib.sha256(encoded({'libraryId':library_id,'items':resources,'assets':assets,'hierarchy':hierarchy})).hexdigest()
    return {'schema':'static-web-bake.resources.v1','title':title,'libraryId':library_id,'revision':revision,'mode':'static','items':resources,'assets':assets,'hierarchy':hierarchy}
