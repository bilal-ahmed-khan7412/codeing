from pathlib import Path

root = Path(__file__).resolve().parent
plan_service = root / 'tracker_services' / 'plan_service.py'
readme = root / 'README.md'

if not plan_service.exists():
    raise SystemExit('tracker_services/plan_service.py not found. Run this patch inside intern_tracker_system_v0.')

s = plan_service.read_text(encoding='utf-8')

marker_start = 'def _v54_extend_intern_with_plan('
start = s.find(marker_start)
if start == -1:
    raise SystemExit('Could not find _v54_extend_intern_with_plan in plan_service.py. Apply v54/v55/v56/v57/v58 first.')
end = s.find('PlanService.extend_intern_with_plan = _v54_extend_intern_with_plan', start)
if end == -1:
    raise SystemExit('Could not find end of _v54_extend_intern_with_plan block.')
block = s[start:end]

# Replace the fragile RenderService/VersionService fallback block with dynamic lookup.
old_block_start = block.find('    # Use the module-level RenderService and VersionService if they already exist.')
old_block_end = block.find('    intern_name = (intern_name or', old_block_start)
if old_block_start != -1 and old_block_end != -1:
    new_lookup = r'''    # v0.59 robust dynamic service lookup.
    # The project has changed renderer module paths across versions, so do not
    # hardcode tracker_excel.renderer.render_service or tracker_excel.renderer.
    import importlib
    import pkgutil

    def _find_class_in_package(package_name: str, class_name: str):
        try:
            package = importlib.import_module(package_name)
        except Exception:
            return None
        if hasattr(package, class_name):
            return getattr(package, class_name)
        package_path = getattr(package, '__path__', None)
        if not package_path:
            return None
        for mod in pkgutil.iter_modules(package_path, package.__name__ + '.'):
            try:
                module = importlib.import_module(mod.name)
            except Exception:
                continue
            if hasattr(module, class_name):
                return getattr(module, class_name)
        return None

    render_service_cls = globals().get('RenderService') or _find_class_in_package('tracker_excel.renderer', 'RenderService')
    version_service_cls = globals().get('VersionService')
    if version_service_cls is None:
        try:
            version_mod = importlib.import_module('tracker_services.version_service')
            version_service_cls = getattr(version_mod, 'VersionService')
        except Exception:
            version_service_cls = None
    if render_service_cls is None:
        return CommandResult(False, 'RenderService could not be located in tracker_excel.renderer package')
    if version_service_cls is None:
        return CommandResult(False, 'VersionService could not be located')

'''
    block = block[:old_block_start] + new_lookup + block[old_block_end:]
else:
    # Insert lookup after InternSheetDrafter import if previous block shape changed.
    needle = "    from tracker_chat.intern_sheet_drafter import InternSheetDrafter\n\n"
    if needle not in block:
        raise SystemExit('Could not find import insertion point for dynamic lookup.')
    new_lookup = r'''    from tracker_chat.intern_sheet_drafter import InternSheetDrafter

    # v0.59 robust dynamic service lookup.
    import importlib
    import pkgutil

    def _find_class_in_package(package_name: str, class_name: str):
        try:
            package = importlib.import_module(package_name)
        except Exception:
            return None
        if hasattr(package, class_name):
            return getattr(package, class_name)
        package_path = getattr(package, '__path__', None)
        if not package_path:
            return None
        for mod in pkgutil.iter_modules(package_path, package.__name__ + '.'):
            try:
                module = importlib.import_module(mod.name)
            except Exception:
                continue
            if hasattr(module, class_name):
                return getattr(module, class_name)
        return None

    render_service_cls = globals().get('RenderService') or _find_class_in_package('tracker_excel.renderer', 'RenderService')
    version_service_cls = globals().get('VersionService')
    if version_service_cls is None:
        try:
            version_mod = importlib.import_module('tracker_services.version_service')
            version_service_cls = getattr(version_mod, 'VersionService')
        except Exception:
            version_service_cls = None
    if render_service_cls is None:
        return CommandResult(False, 'RenderService could not be located in tracker_excel.renderer package')
    if version_service_cls is None:
        return CommandResult(False, 'VersionService could not be located')

'''
    block = block.replace(needle, new_lookup, 1)

# Replace usage inside only this function block.
block = block.replace('out = output_path or VersionService.next_version_path(source_path)', 'out = output_path or version_service_cls.next_version_path(source_path)')
block = block.replace('RenderService.render_data(data, out)', 'render_service_cls.render_data(data, out)')

s = s[:start] + block + s[end:]
plan_service.write_text(s, encoding='utf-8')

try:
    import py_compile
    py_compile.compile(str(plan_service), doraise=True)
except Exception as e:
    raise SystemExit(f'plan_service.py compile failed after v0.59 patch: {e}')

if readme.exists():
    readme.write_text(readme.read_text(encoding='utf-8') + r'''

## v0.59 Dynamic RenderService lookup for Extend Intern With Plan

- Fixes runtime error:
  `cannot import name RenderService from tracker_excel.renderer`.
- The extension workflow now dynamically scans `tracker_excel.renderer` for a `RenderService` class instead of hardcoding a module path.
- Also dynamically resolves `VersionService`.
''', encoding='utf-8')

print('v0.59 dynamic RenderService lookup patch applied successfully.')
