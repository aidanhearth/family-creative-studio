import pytest
from studio.runtime import browser_executable

def test_explicit_missing_browser_is_not_silently_replaced(monkeypatch):
    monkeypatch.setenv("STUDIO_BROWSER", "/missing/browser")
    monkeypatch.setattr("studio.runtime.shutil.which", lambda name: None)
    with pytest.raises(FileNotFoundError, match="STUDIO_BROWSER"):
        browser_executable()

def test_chromium_fallback(monkeypatch):
    monkeypatch.delenv("STUDIO_BROWSER", raising=False)
    monkeypatch.setattr("studio.runtime.shutil.which", lambda name: "/usr/bin/chromium" if name == "chromium" else None)
    assert browser_executable() == "/usr/bin/chromium"

def test_browser_alias_is_absolute_without_losing_argv_zero(tmp_path, monkeypatch):
    target=tmp_path/'multicall';target.write_text('');target.chmod(0o700)
    alias=tmp_path/'chromium';alias.symlink_to(target)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('STUDIO_BROWSER','./chromium')
    assert browser_executable()==str(alias)

def test_render_environment_pins_relative_operator_paths(tmp_path, monkeypatch):
    from studio.store import Store
    from studio.runner import Runner
    from studio.paths import SOURCES
    monkeypatch.setenv('STUDIO_SOURCES','.sources')
    monkeypatch.setenv('STUDIO_DATA','.state')
    monkeypatch.delenv('STUDIO_BROWSER',raising=False)
    store=Store(tmp_path/'state')
    runner=Runner(store,{'id':'test'},tmp_path/'job')
    assert runner.env['STUDIO_SOURCES']==str(SOURCES)
    assert runner.env['STUDIO_DATA']==str(store.root.resolve())

def test_background_worker_does_not_reinterpret_relative_state(tmp_path,monkeypatch):
    import studio.cli as cli
    from studio.store import Store
    monkeypatch.setenv('STUDIO_DATA','.state')
    monkeypatch.setenv('STUDIO_SOURCES','.sources')
    monkeypatch.delenv('STUDIO_BROWSER',raising=False)
    calls=[]
    monkeypatch.setattr(cli.subprocess,'Popen',lambda *args,**kwargs:calls.append(kwargs))
    store=Store(tmp_path/'state')
    cli.ensure_worker(store)
    assert calls[0]['env']['STUDIO_DATA']==str(store.root.resolve())
    assert calls[0]['env']['STUDIO_SOURCES']==str(cli.SOURCES)
