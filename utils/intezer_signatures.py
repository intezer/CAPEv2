#!/usr/bin/env python
# Copyright (C) 2010-2015 Cuckoo Foundation.
# This file is part of Cuckoo Sandbox - http://www.cuckoosandbox.org
# See the file 'docs/LICENSE' for copying permission.
import argparse
import os
import sys

if sys.version_info[:2] < (3, 6):
    sys.exit("You are running an incompatible version of Python, please use >= 3.6")
import logging
import tarfile
import requests
from io import BytesIO

sys.path.append(os.path.join(os.path.abspath(os.path.dirname(__file__)), ".."))

import lib.cuckoo.common.colors as colors
from lib.cuckoo.common.constants import CUCKOO_ROOT

log = logging.getLogger(__name__)
URL = "https://api.github.com/repos/intezer/cape-signatures/tarball"


def _copy_files_to_directory(tar, src_prefix, dst_prefix, tar_members):
    for member in tar_members:
        if not member.name.startswith(src_prefix) or member.name == src_prefix:
            continue

        filepath = os.path.join(dst_prefix, member.name[len(src_prefix) + 1:])
        open(filepath, "wb").write(tar.extractfile(member).read())
        print('File "{}" {}'.format(filepath, colors.green("installed")))


def download(user: str, password: str, path: str = None):
    try:
        if not path:
            data = requests.get(URL, auth=(user, password), stream=True).raw.read()
            tar = tarfile.TarFile.open(fileobj=BytesIO(data), mode="r:gz")
        else:
            tar = tarfile.TarFile.open(name=path, mode="r:gz")
    except Exception as e:
        print("ERROR: Unable to download archive: %s" % e)
        sys.exit(-1)

    members = tar.getmembers()
    directory = members[0].name.split("/")[0]
    signature_prefix = f'{directory}/signatures'
    allow_list_members_prefix = f'{directory}/allow_lists'
    signature_dest = os.path.join(CUCKOO_ROOT, 'modules', 'signatures')
    allow_list_dest = os.path.join(CUCKOO_ROOT, 'extra')

    _copy_files_to_directory(tar, signature_prefix, signature_dest, members)
    _copy_files_to_directory(tar, allow_list_members_prefix, allow_list_dest, members)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-u", "--user", help="User name in bitbucket", type=str, required=False)
    parser.add_argument("-p", "--password", help="App password in bitbucket", type=str, required=False)
    parser.add_argument("-f", "--file", help="Path to cape-signatures repo", type=str, required=False)
    args = parser.parse_args()

    download(args.user, args.password, args.file)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
