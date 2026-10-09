"""Build-time installation of pinned Oracle-published software, never runtime secrets."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path
from urllib.request import urlopen

JARS = ("oraclepki.jar", "osdt_core.jar", "osdt_cert.jar")


def download(artifact, destination):
    algorithm = "sha256" if "sha256" in artifact else "sha1"
    checksum = hashlib.new(algorithm)
    sha256 = hashlib.sha256()
    with urlopen(artifact["url"], timeout=120) as source, destination.open("xb") as output:
        while data := source.read(1024 * 1024):
            checksum.update(data)
            sha256.update(data)
            output.write(data)
    if checksum.hexdigest() != artifact[algorithm]:
        destination.unlink()
        raise ValueError("Oracle artifact checksum mismatch")
    return sha256.hexdigest()


def wallet_jars(archive, destination):
    with tarfile.open(archive, "r:gz") as bundle:
        for name in JARS:
            matches = [member for member in bundle.getmembers()
                       if member.isfile() and Path(member.name).name == name]
            if len(matches) != 1:
                raise ValueError("Oracle wallet archive missing an unambiguous required JAR")
            # Extract file content only, never archive paths, symlinks, or ownership.
            with bundle.extractfile(matches[0]) as source, (destination / name).open("xb") as output:
                shutil.copyfileobj(source, output)


def install(manifest_path, destination, architecture):
    manifest = json.loads(manifest_path.read_text())
    if architecture != manifest["architecture"]:
        raise ValueError("Pinned Oracle Client build supports linux/amd64 only")
    if destination.exists():
        raise ValueError("Oracle Client destination must not already exist")
    with tempfile.TemporaryDirectory(prefix="oracle-build-") as temporary:
        scratch = Path(temporary)
        hashes = {}
        for name in ("basic", "sqlplus", "wallet_jars"):
            archive = scratch / name
            hashes[name] = download(manifest[name], archive)
        extracted = scratch / "extracted"
        extracted.mkdir()
        # Both ZIP archives are verified before using the vendor's archive layout.
        for name in ("basic", "sqlplus"):
            subprocess.run(["unzip", "-q", "-o", str(scratch / name), "-d", str(extracted)], check=True)
        directories = list(extracted.glob("instantclient_*"))
        if len(directories) != 1 or not (directories[0] / "libclntsh.so").exists():
            raise ValueError("Oracle Instant Client archive has an unexpected layout")
        destination.mkdir(parents=True)
        shutil.copytree(directories[0], destination / "lib", symlinks=True)
        (destination / "bin").mkdir()
        (destination / "bin/sqlplus").symlink_to("../lib/sqlplus")
        (destination / "jlib").mkdir()
        wallet_jars(scratch / "wallet_jars", destination / "jlib")
        (destination / "manifest.json").write_text(json.dumps({**manifest, "download_sha256": hashes}, indent=2) + "\n")
    print("Pinned Oracle Client, SQL*Plus and wallet JARs installed into the image build stage.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--architecture", required=True)
    parser.add_argument("--destination", type=Path, default=Path("/opt/oracle/client"))
    args = parser.parse_args()
    install(Path(__file__).with_name("artifacts.json"), args.destination, args.architecture)
