"""YAML lesen und schreiben: PyYAML, falls installiert, sonst der eingebaute Leser."""

try:
    import yaml  # optional
except ImportError:  # pragma: no cover - abhängig von der Umgebung
    yaml = None

from .miniyaml import MiniYAMLError, mini_dump, mini_load

BACKEND = "PyYAML" if yaml is not None else "eingebaut"


def _unique_key_loader():
    """SafeLoader, der doppelte Schlüssel als Fehler meldet."""

    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader, node, deep=False):
        seen = {}
        for key_node, _ in node.value:
            key = loader.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(
                    "beim Lesen eines Mappings",
                    node.start_mark,
                    "doppelter Schlüssel '%s' (zuerst in Zeile %d)" % (key, seen[key] + 1),
                    key_node.start_mark,
                )
            seen[key] = key_node.start_mark.line
        return yaml.SafeLoader.construct_mapping(loader, node, deep)

    UniqueKeyLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping)
    # Unquotiertes '=' (YAML 1.1 value-Tag) wie einen normalen String behandeln
    UniqueKeyLoader.add_constructor("tag:yaml.org,2002:value", lambda ldr, node: ldr.construct_scalar(node))
    return UniqueKeyLoader


def dump(value):
    if yaml is None:
        return mini_dump(value)
    return yaml.safe_dump(
        value, default_flow_style=False, sort_keys=False, allow_unicode=True, width=1000
    ).rstrip("\n")


def load_yaml(text, strict=True):
    """Liest YAML mit PyYAML (falls vorhanden) oder dem eingebauten Leser.
    strict=False: doppelte Schlüssel erlaubt (späterer Wert gilt), mit Warnung."""
    warnings = []
    if yaml is None:
        if strict:
            return mini_load(text), warnings
        try:
            return mini_load(text), warnings
        except MiniYAMLError as e:
            if "doppelter" not in str(e):
                raise
            return mini_load(text, allow_dup=True, warnings=warnings), warnings
    try:
        return yaml.load(text, Loader=_unique_key_loader()), warnings
    except yaml.constructor.ConstructorError as e:
        if strict or "doppelter" not in str(e):
            raise
        loader = type("PermissiveLoader", (yaml.SafeLoader,), {})
        loader.add_constructor("tag:yaml.org,2002:value", lambda ldr, node: ldr.construct_scalar(node))
        return yaml.load(text, Loader=loader), [
            "Doppelte Schlüssel gefunden – jeweils der spätere Wert gilt."
        ]
