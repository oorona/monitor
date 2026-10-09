"""Shared reader validation; no database, vendor tooling or real credentials required."""
import json
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import pytest
try:
    from app import shared_wallet as wallet
except ModuleNotFoundError:
    import shared_wallet as wallet


def fixture(tmp_path):
    root=tmp_path/'wallet'; directory=root/'.generations'/str(uuid4())
    directory.mkdir(parents=True)
    records={alias:{'account':account,'privilege':'normal','dbid':'123','db_unique_name':'TEST',
        'container':'PDB','host':'db.internal','port':1521,'service':'PDB'}
        for alias,account in [('reports','REPORT_RO'),('audits','AUDIT_RO')]}
    for name in wallet.BUNDLE_FILES:
        (directory/name).write_bytes(b'encrypted-test-fixture')
        (directory/name).chmod(0o600)
    (directory/'entries.json').write_text(json.dumps({'version':1,'entries':records}))
    (root/'current').symlink_to('.generations/'+directory.name)
    return root,directory


def test_aliases_pin_the_same_snapshot_and_secret_stays_in_private_pipe(tmp_path,monkeypatch):
    root,directory=fixture(tmp_path)
    assert wallet.resolve_wallet(root,'reports')==wallet.resolve_wallet(root,'audits')==directory
    calls=[]
    def read(args,**kwargs):
        calls.append((args,kwargs))
        return SimpleNamespace(returncode=0,stdout=b'Fixture9_private',stderr=b'')
    monkeypatch.setattr(wallet.subprocess,'run',read)
    assert wallet.read_credentials(directory,'reports')==('REPORT_RO','Fixture9_private')
    args,options=calls[0]
    assert args[-1]=='watchword.password.reports'
    assert options['stdin']==subprocess.DEVNULL
    assert options['stdout']==subprocess.PIPE and options['stderr']==subprocess.PIPE
    assert options['timeout']==10
    assert 'Fixture9_private' not in str(args)+str(options)
    assert all(b'Fixture9_private' not in f.read_bytes() for f in directory.iterdir())


def test_reader_errors_never_expose_vendor_output(tmp_path,monkeypatch):
    _,directory=fixture(tmp_path)
    monkeypatch.setattr(wallet.subprocess,'run',lambda *args,**kwargs:SimpleNamespace(returncode=1,stdout=b'SECRET_ECHO',stderr=b'SECRET_ECHO'))
    with pytest.raises(wallet.SharedWalletError) as error:wallet.read_credentials(directory,'reports')
    assert 'SECRET_ECHO' not in str(error.value)


def test_missing_entry_unsafe_files_and_escape_pointer_fail_closed(tmp_path):
    root,directory=fixture(tmp_path)
    with pytest.raises(wallet.SharedWalletError):wallet.resolve_wallet(root,'missing')
    (directory/'cwallet.sso').chmod(0o644)
    with pytest.raises(wallet.SharedWalletError):wallet.resolve_wallet(root,'reports')
    (directory/'cwallet.sso').chmod(0o600)
    (root/'current').unlink();(root/'current').symlink_to(tmp_path)
    with pytest.raises(wallet.SharedWalletError):wallet.resolve_wallet(root,'reports')


def test_registry_alias_is_global_across_apps_and_can_be_shared_on_one_database(tmp_path):
    try:
        from app.suite_registry import Access, DatabaseInput, Registry, RegistryConflict
    except ModuleNotFoundError:
        from suite_registry import Access, DatabaseInput, Registry, RegistryConflict
    registry=Registry(tmp_path)
    registry.save(DatabaseInput(name='first',host='db',service_or_sid='PDB',access={
        'rollcall':Access(alias='reports'),'monitor':Access(alias='reports')}),'watchword')
    with pytest.raises(RegistryConflict):
        registry.save(DatabaseInput(name='second',host='other',service_or_sid='OTHER',access={
            'muster':Access(alias='reports')}),'watchword')
    assert len(registry.read().databases)==1


@pytest.mark.parametrize('change', [{'password':'not-allowed'}, {'privilege':'unknown'}, {'port':True}, {'host':'bad)host'}, {'dbid':123}])
def test_invalid_or_secret_bearing_metadata_is_rejected(tmp_path,change):
    root,directory=fixture(tmp_path)
    path=directory/'entries.json';document=json.loads(path.read_text())
    document['entries']['reports'].update(change);path.write_text(json.dumps(document))
    with pytest.raises(wallet.SharedWalletError):wallet.resolve_wallet(root,'reports')
