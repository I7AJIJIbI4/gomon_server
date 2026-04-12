#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Drive integration for GomonClinic.
Creates per-client/per-visit photo folders and shares them.

Uses Service Account auth via openssl JWT signing (no pip packages needed).
"""

import json
import time
import base64
import subprocess
import tempfile
import os
import logging
import re
import requests

logger = logging.getLogger('gdrive')

SA_KEY_FILE = '/home/gomoncli/private_data/gdrive_sa.json'
ROOT_FOLDER_ID = '1Cj2MseN7toVQ_R4u8_PBVDnKAfngOA-N'
DRIVE_API = 'https://www.googleapis.com/drive/v3'

# Token cache
_token = None
_token_exp = 0


def _get_access_token():
    """Get Google API access token via Service Account JWT. Cached for 50 min."""
    global _token, _token_exp
    if _token and time.time() < _token_exp:
        return _token

    sa = json.load(open(SA_KEY_FILE))
    header = base64.urlsafe_b64encode(
        json.dumps({"alg": "RS256", "typ": "JWT"}).encode()
    ).rstrip(b"=")
    now = int(time.time())
    claims = base64.urlsafe_b64encode(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/drive",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now,
        "exp": now + 3600,
    }).encode()).rstrip(b"=")
    sign_input = header + b"." + claims

    # Sign with openssl (works on any Linux, no pip packages)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.pem', delete=False) as f:
        f.write(sa['private_key'])
        keyfile = f.name
    try:
        proc = subprocess.Popen(
            ['openssl', 'dgst', '-sha256', '-sign', keyfile],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = proc.communicate(sign_input, timeout=10)
    finally:
        os.unlink(keyfile)

    if proc.returncode != 0:
        raise RuntimeError('openssl sign failed: {}'.format(err.decode()))

    sig = base64.urlsafe_b64encode(out).rstrip(b"=")
    jwt_token = (sign_input + b"." + sig).decode()

    r = requests.post('https://oauth2.googleapis.com/token', data={
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': jwt_token,
    }, timeout=10)
    data = r.json()
    if 'access_token' not in data:
        raise RuntimeError('Google auth failed: {}'.format(data))

    _token = data['access_token']
    _token_exp = time.time() + 3000  # refresh after 50 min
    return _token


def _headers():
    return {'Authorization': 'Bearer ' + _get_access_token()}


def _sanitize_name(name):
    """Remove characters illegal in Drive folder names."""
    return re.sub(r'[/\\<>:"|?*]', '_', (name or 'Unknown').strip()) or 'Unknown'


def _find_folder(name, parent_id):
    """Find existing folder by name inside parent. Returns folder_id or None."""
    q = "name='{}' and '{}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false".format(
        name.replace("'", "\\'"), parent_id)
    r = requests.get(DRIVE_API + '/files', params={
        'q': q, 'fields': 'files(id)', 'pageSize': 1
    }, headers=_headers(), timeout=10)
    files = r.json().get('files', [])
    return files[0]['id'] if files else None


def _create_folder(name, parent_id):
    """Create a folder in Google Drive. Returns folder_id."""
    r = requests.post(DRIVE_API + '/files', json={
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }, headers=_headers(), timeout=10)
    data = r.json()
    if 'id' not in data:
        raise RuntimeError('Create folder failed: {}'.format(data))
    return data['id']


def _find_or_create_folder(name, parent_id):
    """Find existing folder or create new one."""
    folder_id = _find_folder(name, parent_id)
    if folder_id:
        return folder_id
    return _create_folder(name, parent_id)


def _share_anyone_editor(folder_id):
    """Make folder accessible to anyone with link as editor."""
    requests.post(
        DRIVE_API + '/files/{}/permissions'.format(folder_id),
        json={'type': 'anyone', 'role': 'writer'},
        headers=_headers(), timeout=10)


def _get_web_link(folder_id):
    """Get webViewLink for a folder."""
    r = requests.get(
        DRIVE_API + '/files/{}'.format(folder_id),
        params={'fields': 'webViewLink'},
        headers=_headers(), timeout=10)
    return r.json().get('webViewLink', 'https://drive.google.com/drive/folders/{}'.format(folder_id))


def count_files_in_folder(folder_id):
    """Count non-folder files in a Drive folder."""
    try:
        r = requests.get(DRIVE_API + '/files', params={
            'q': "'{}' in parents and mimeType!='application/vnd.google-apps.folder' and trashed=false".format(folder_id),
            'fields': 'files(id)',
            'pageSize': 100,
        }, headers=_headers(), timeout=10)
        return len(r.json().get('files', []))
    except Exception:
        return 0


def list_files_in_folder(folder_id, recursive=False):
    """List image/video files in a folder. Returns [{id, name, mimeType, thumbnailLink, createdTime}]."""
    try:
        q = "'{}' in parents and trashed=false".format(folder_id)
        if not recursive:
            q += " and mimeType!='application/vnd.google-apps.folder'"
        r = requests.get(DRIVE_API + '/files', params={
            'q': q,
            'fields': 'files(id,name,mimeType,thumbnailLink,createdTime)',
            'pageSize': 100,
            'orderBy': 'createdTime',
        }, headers=_headers(), timeout=10)
        files = r.json().get('files', [])
        if recursive:
            # Also list files in subfolders (До/Після)
            subfolders = [f for f in files if f.get('mimeType') == 'application/vnd.google-apps.folder']
            result = [f for f in files if f.get('mimeType') != 'application/vnd.google-apps.folder']
            for sf in subfolders:
                sub_files = list_files_in_folder(sf['id'], recursive=False)
                for sf_file in sub_files:
                    sf_file['subfolder'] = sf.get('name', '')
                result.extend(sub_files)
            return result
        return files
    except Exception as e:
        logger.error('list_files error: {}'.format(e))
        return []


def get_client_all_photos(client_name):
    """Get all photos for a client across all visit folders. Returns [{visit, subfolder, id, name, thumbnailLink, createdTime}]."""
    safe_client = _sanitize_name(client_name)
    client_folder_id = _find_folder(safe_client, ROOT_FOLDER_ID)
    if not client_folder_id:
        return []

    # List visit subfolders
    try:
        r = requests.get(DRIVE_API + '/files', params={
            'q': "'{}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false".format(client_folder_id),
            'fields': 'files(id,name)',
            'pageSize': 50,
            'orderBy': 'name',
        }, headers=_headers(), timeout=10)
        visit_folders = r.json().get('files', [])
    except Exception:
        return []

    all_photos = []
    for vf in visit_folders:
        files = list_files_in_folder(vf['id'], recursive=True)
        for f in files:
            f['visit'] = vf.get('name', '')
            f['visit_folder_id'] = vf['id']
        all_photos.extend(files)

    # Sort chronologically
    all_photos.sort(key=lambda x: x.get('createdTime', ''))
    return all_photos


def create_visit_folder(client_name, date, procedure_name):
    """
    Create folder structure: GomonClinic / ClientName / YYYY-MM-DD_Procedure / До + Після
    Returns (visit_folder_url, client_folder_url). До/Після subfolders are created but URLs not returned.
    """
    safe_client = _sanitize_name(client_name)
    safe_proc = _sanitize_name(procedure_name)
    visit_name = '{}_{}'.format(date, safe_proc)

    # GomonClinic / ClientName
    client_folder_id = _find_or_create_folder(safe_client, ROOT_FOLDER_ID)

    # GomonClinic / ClientName / YYYY-MM-DD_ProcedureName
    visit_folder_id = _find_or_create_folder(visit_name, client_folder_id)

    # GomonClinic / ClientName / YYYY-MM-DD_ProcedureName / До
    before_id = _find_or_create_folder('До', visit_folder_id)
    # GomonClinic / ClientName / YYYY-MM-DD_ProcedureName / Після
    after_id = _find_or_create_folder('��ісля', visit_folder_id)

    # Share visit folder with anyone (editor) — subfolders inherit
    _share_anyone_editor(visit_folder_id)

    visit_url = _get_web_link(visit_folder_id)
    client_url = _get_web_link(client_folder_id)
    before_url = _get_web_link(before_id)
    after_url = _get_web_link(after_id)

    logger.info('Drive folder created: {} → {}'.format(visit_name, visit_url))
    return visit_url, client_url
