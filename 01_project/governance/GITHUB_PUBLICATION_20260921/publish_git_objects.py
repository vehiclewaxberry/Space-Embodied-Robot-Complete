"""Resume the authorized publication using verified Git objects and a final ref switch.

Credentials stay in memory. Checkpoints contain only public object identities.
"""
from pathlib import Path
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
import argparse, base64, hashlib, json, os, subprocess, threading, time, tempfile
import urllib.request, urllib.error

A = Path(__file__).resolve().parent
P = A.parents[2] / '20_engineering/SERVICE_STAR_PUBLICATION_20260921'
REPO = 'vehiclewaxberry/Space-Embodied-Robot-Complete'
OLD = 'fe83adeb2c042568e3fe84a3a7a060a3966133d0'
EXPECTED = '359fa6cd1bc869bbcccdd9a2dedc73ee1a3cee0e'
TREE = '2a57db005a37e7059377931a069addf46a89e1a6'
GIT = ['git', '-c', 'safe.directory=' + P.as_posix(), '-C', str(P)]
CHECKPOINT = A / 'GITHUB_OBJECT_UPLOAD_CHECKPOINT.json'
lock = threading.Lock()
rate_lock = threading.Lock()
next_request = 0.0
token = None

def git(*args):
    return subprocess.check_output(GIT + list(args))

def call(method, path, payload=None):
    global next_request
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8') if payload is not None else None
    for attempt in range(3):
        if method != 'GET':
            with rate_lock:
                delay = max(0, next_request - time.monotonic())
                next_request = max(next_request, time.monotonic()) + 0.85
            if delay: time.sleep(delay)
        # Windows curl uses the verified working Schannel transport. The token is
        # supplied through stdin configuration, never command arguments or disk.
        config = [
            'url = ' + json.dumps('https://api.github.com/repos/' + REPO + path),
            'request = ' + json.dumps(method),
            'header = "Accept: application/vnd.github+json"',
            'header = "X-GitHub-Api-Version: 2022-11-28"',
            'header = "User-Agent: Hardware-Publication-Verification"',
            'header = "Content-Type: application/json"',
            'http1.1', 'silent', 'show-error', 'fail-with-body',
            'connect-timeout = 15', 'max-time = 180',
        ]
        if token: config.append('header = ' + json.dumps('Authorization: Bearer ' + token))
        temporary = None
        try:
            if data is not None:
                with tempfile.NamedTemporaryFile(dir=A, prefix='public_git_payload_', suffix='.json', delete=False) as f:
                    f.write(data); temporary = Path(f.name)
                config.append('data-binary = ' + json.dumps('@' + temporary.as_posix()))
            response = subprocess.run(['curl.exe', '--config', '-'], input=('\n'.join(config) + '\n').encode(), capture_output=True, timeout=195)
            if response.returncode:
                print(json.dumps({'event': 'curl_retry', 'method': method, 'path': path, 'curl_exit': response.returncode, 'attempt': attempt + 1}), flush=True)
                # Server error messages exclude the credential-bearing request.
                if response.returncode == 22:
                    try: message = json.loads(response.stdout).get('message', '')
                    except ValueError: message = 'unparsed server error'
                    print(json.dumps({'event': 'server_error', 'message': message[:300]}), flush=True)
                if attempt == 2: raise RuntimeError('GitHub curl request did not complete')
            else:
                return json.loads(response.stdout)
        except (OSError, ValueError) as exc:
            print(json.dumps({'event': 'transport_retry', 'method': method, 'path': path, 'exception_type': type(exc).__name__, 'attempt': attempt + 1}), flush=True)
            if attempt == 2: raise RuntimeError('GitHub transport did not complete') from None
        finally:
            if temporary is not None:
                assert temporary.parent == A and temporary.name.startswith('public_git_payload_')
                temporary.unlink(missing_ok=True)
        time.sleep(3 * (attempt + 1))

def main():
    global token
    parser = argparse.ArgumentParser()
    parser.add_argument('--upload', action='store_true')
    parser.add_argument('--finalize', action='store_true')
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    assert git('rev-parse', 'HEAD').decode().strip() == EXPECTED
    assert git('rev-parse', 'HEAD^{tree}').decode().strip() == TREE
    assert not git('status', '--porcelain').strip()
    rows = []
    for entry in git('ls-tree', '-r', '-z', 'HEAD').split(b'\0'):
        if not entry: continue
        meta, name = entry.split(b'\t', 1)
        mode, kind, sha = meta.decode().split()
        assert kind == 'blob'
        name = name.decode('utf-8')
        raw = (P / name).read_bytes()
        assert hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == sha, name
        rows.append({'path': name, 'mode': mode, 'type': 'blob', 'sha': sha, 'size': len(raw)})
    assert len(rows) == 989
    env = os.environ.copy(); env.update(GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='never')
    cred = subprocess.run(GIT + ['credential', 'fill'], input='protocol=https\nhost=github.com\n\n', text=True, capture_output=True, env=env, timeout=45)
    if cred.returncode: raise RuntimeError('Existing credential unavailable; no credential logged')
    token = dict(line.split('=', 1) for line in cred.stdout.splitlines() if '=' in line).get('password')
    if not token: raise RuntimeError('Existing credential unavailable')
    remote = call('GET', '/git/ref/heads/main')['object']['sha']
    if remote == EXPECTED:
        print(json.dumps({'event': 'already_published', 'commit': remote}), flush=True)
        return
    assert remote == OLD, 'Remote branch changed; refusing overwrite'
    checkpoint = json.loads(CHECKPOINT.read_text('utf-8')) if CHECKPOINT.exists() else {'repository': REPO, 'tree': TREE, 'blobs': {}, 'status': 'UPLOADING'}
    assert checkpoint['repository'] == REPO and checkpoint['tree'] == TREE
    known = checkpoint['blobs']
    if not checkpoint.get('old_tree_checked'):
        old_tree = call('GET', '/git/trees/' + OLD + '?recursive=1')
        assert old_tree.get('truncated') is False
        relevant = {r['sha'] for r in rows}
        for row in old_tree['tree']:
            if row['type'] == 'blob' and row['sha'] in relevant:
                known[row['sha']] = {'source': 'existing_remote_tree'}
        checkpoint['old_tree_checked'] = True

    def save():
        checkpoint['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temp = CHECKPOINT.with_suffix('.tmp')
        temp.write_text(json.dumps(checkpoint, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        temp.replace(CHECKPOINT)

    def acknowledge(sha, source, size):
        with lock:
            known[sha] = {'source': source, 'size': size}
            save()

    pending = {}
    inline = []
    for row in rows:
        if row['sha'] in known or row['sha'] in pending: continue
        raw = (P / row['path']).read_bytes()
        try: content = raw.decode('utf-8')
        except UnicodeDecodeError: content = None
        if content is not None and len(raw) <= 262144:
            inline.append((row, content))
        else: pending[row['sha']] = row
    print(json.dumps({'event': 'inventory', 'files': len(rows), 'acknowledged_blobs': len(known), 'pending_blob_requests': len(pending), 'pending_inline_text': len(inline)}), flush=True)
    save()
    if args.upload:
        # Largest files first exposes transport limits before hundreds of requests.
        work = sorted(pending.values(), key=lambda r: r['size'], reverse=True)
        if args.limit is not None: work = work[:args.limit]
        done = 0
        def upload(row):
            raw = (P / row['path']).read_bytes()
            try: payload = {'content': raw.decode('utf-8'), 'encoding': 'utf-8'}
            except UnicodeDecodeError: payload = {'content': base64.b64encode(raw).decode('ascii'), 'encoding': 'base64'}
            result = call('POST', '/git/blobs', payload)
            assert result['sha'] == row['sha'], row['path']
            acknowledge(row['sha'], 'created_blob_api', row['size'])
            return row
        failures = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs = {pool.submit(upload, r): r for r in work}
            for job in as_completed(jobs):
                try:
                    row = job.result(); done += 1
                    if done <= 10 or done % 20 == 0 or row['size'] > 2_000_000:
                        print(json.dumps({'event': 'blob_acknowledged', 'completed_this_run': done, 'requests_this_run': len(work), 'bytes': row['size'], 'path': row['path']}), flush=True)
                except Exception as exc:
                    failures.append({'path': jobs[job]['path'], 'error_type': type(exc).__name__})
                    print(json.dumps({'event': 'blob_failed', **failures[-1]}), flush=True)
                    # Fail closed: cancel requests that have not begun; retain successful objects.
                    for future in jobs: future.cancel()
                    break
        if failures:
            checkpoint['last_failures'] = failures; save()
            raise RuntimeError('Upload incomplete; checkpoint retained')
        if args.limit is not None:
            print(json.dumps({'event': 'limited_probe_complete', 'acknowledged_blobs': len(known)}), flush=True)
            return
        batch = []; batch_size = 0
        def flush_text(items):
            elements = [{'path': r['path'], 'mode': r['mode'], 'type': 'blob', 'content': c} for r, c in items]
            result = call('POST', '/git/trees', {'tree': elements})
            actual = call('GET', '/git/trees/' + result['sha'] + '?recursive=1')
            assert actual.get('truncated') is False
            mapped = {r['path']: r['sha'] for r in actual['tree'] if r['type'] == 'blob'}
            assert mapped == {r['path']: r['sha'] for r, c in items}
            for row, content in items: acknowledge(row['sha'], 'created_inline_tree_api', row['size'])
            print(json.dumps({'event': 'text_batch_acknowledged', 'files': len(items), 'acknowledged_blobs': len(known)}), flush=True)
        for row, content in inline:
            if row['sha'] in known: continue
            if batch and batch_size + row['size'] > 500000:
                flush_text(batch); batch = []; batch_size = 0
            batch.append((row, content)); batch_size += row['size']
        if batch: flush_text(batch)
    missing = [r['path'] for r in rows if r['sha'] not in known]
    checkpoint['missing_paths'] = missing
    save()
    print(json.dumps({'event': 'object_coverage', 'covered_files': len(rows) - len(missing), 'missing_files': len(missing)}), flush=True)
    if not args.finalize: return
    assert not missing, 'Cannot update main before every file object is acknowledged'
    tree_result = call('POST', '/git/trees', {'tree': [{k: r[k] for k in ('path', 'mode', 'type', 'sha')} for r in rows]})
    assert tree_result['sha'] == TREE, 'Remote tree differs from reviewed local tree'
    author = {'name': 'vehiclewaxberry', 'email': '126759605+vehiclewaxberry@users.noreply.github.com', 'date': '2026-09-21T19:42:17+09:00'}
    result = call('POST', '/git/commits', {'message': 'Publish space service robot hardware design and long-term project roadmap\n', 'tree': TREE, 'parents': [], 'author': author, 'committer': author})
    checkpoint['api_commit'] = result['sha']; checkpoint['status'] = 'OBJECTS_AND_COMMIT_COMPLETE'; save()
    assert result['sha'] == EXPECTED, 'API commit identity differs; no ref changed'
    # Final read immediately before the authorized main replacement.
    current = call('GET', '/git/ref/heads/main')['object']['sha']
    assert current in (OLD, EXPECTED), 'Remote main changed; refusing overwrite'
    if current == OLD:
        updated = call('PATCH', '/git/refs/heads/main', {'sha': EXPECTED, 'force': True})
        assert updated['object']['sha'] == EXPECTED
    confirmed = call('GET', '/git/ref/heads/main')['object']['sha']
    assert confirmed == EXPECTED
    checkpoint['status'] = 'MAIN_UPDATED_PENDING_INDEPENDENT_VERIFICATION'; save()
    print(json.dumps({'event': 'main_updated', 'commit': confirmed, 'tree': TREE, 'files': len(rows)}), flush=True)

if __name__ == '__main__':
    main()
