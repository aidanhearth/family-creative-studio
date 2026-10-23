"""Cheap document checks shared by submission, previews and render verification."""
from .paths import ROOT
import importlib.util


def contrast_checks(manifest):
    spec = importlib.util.spec_from_file_location('studio_contrast', ROOT / 'vendor/cathrynlavery--diagram-design/contrast.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    paper = module.parse_color(manifest.brand.paper)[0]
    checks = []
    for name in ('ink', 'muted', 'accent'):
        ratio = module.contrast(module.parse_color(getattr(manifest.brand, name))[0], paper)
        if ratio < 4.5:
            raise ValueError(f'{name} text contrast {ratio:.2f} is below 4.5:1; adjust the brand before rendering')
        checks.append({'check': f'contrast-{name}', 'ratio': round(ratio, 3), 'pass': True, 'engine': 'diagram-design'})
    return checks
