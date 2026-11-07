"""Validate the browser contract before enqueueing a Mac policy change."""
def settings_values(values):
    modes = {'download_mode', 'screenshot_mode', 'icloud_mode'}
    allowed = modes | {'installers_enabled', 'installer_days', 'volatile_mode', 'volatile_days'}
    if not isinstance(values, dict) or not values or set(values) - allowed: raise ValueError('알 수 없는 설정입니다.')
    for key, value in values.items():
        if key in modes: valid = value in ('auto', 'review')
        elif key.endswith('_days'): valid = type(value) is int and 1 <= value <= 365
        elif key == 'installers_enabled': valid = type(value) is bool
        else: valid = value in ('off', 'review', 'auto')
        if not valid: raise ValueError('설정 값이 올바르지 않습니다: ' + key)
    return dict(values)
