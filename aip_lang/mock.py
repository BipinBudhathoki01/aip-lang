"""Deterministic schema-shaped fixtures, used only by explicit mock execution."""


def sample_value(spec):
    if spec.fields is not None:
        return {name: sample_value(child) for name, child in spec.fields.items()}
    name = spec.name.lower()
    if name in ('list', 'array'):
        return []
    if name in ('dict', 'map'):
        return {}
    if name in ('int', 'integer'):
        return 0
    if name in ('float', 'number'):
        return 0.0
    if name in ('bool', 'boolean'):
        return False
    return 'Mock value'
